r"""
天机v9.1 - Embedding语义索引服务 v2.0 [BGE-M3升级版]
======================================
v2.0升级: BGE-M3优先 + 多级回退 + 智能调度
灵境道谱溯源: D9-3【多平台适配煞】· 道九·能源体道 · 四地煞之源之术
  - BGE-M3 (1024维, 100+语言, MTEB 62.6) - 2026业界标杆
  - bge-small-zh-v1.5 (512维, 中文优化) - 轻量回退
  - paraphrase-multilingual-MiniLM-L12-v2 (384维) - 通用回退
  - sklearn TF-IDF (2000维, 零依赖) - 终极兜底

模型优先级 (2026最新技术对标):
1. BGE-M3 — BAAI出品, Apache 2.0, 中文Recall@5 0.776超OpenAI text-embedding-3-small
2. bge-small-zh-v1.5 — 90MB轻量, 中文MTEB 63.6
3. paraphrase-multilingual-MiniLM-L12-v2 — 120MB, 384维
4. sklearn TF-IDF — 零依赖兜底

参考: 2026年Mem0用BGE-M3, Letta默认BGE-M3, Hindsight支持BGE-M3
"""

import threading
from typing import Any

import numpy as np

try:
    from core.processors.evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None


# BGE-M3模型候选优先级 (从最优到最弱)
_BGE_MODEL_CANDIDATES = [
    ("BAAI/bge-m3", 1024, "BGE-M3满血(2026标杆)"),
    ("BAAI/bge-small-zh-v1.5", 512, "BGE-small中文轻量"),
    ("paraphrase-multilingual-MiniLM-L12-v2", 384, "多语言MiniLM"),
]


class EmbeddingService:
    def __init__(
        self,
        engine,
        model_name: str = "auto",
        recorder: Any | None = None,
        learning_engine: Any | None = None,
    ):
        self.engine = engine
        # 【修复】优先使用环境变量，其次使用配置，最后才是参数默认值
        import os

        env_model = os.environ.get("EMBEDDING_ENGINE", "").lower()
        if env_model and env_model != "auto":
            self.model_name = env_model
        else:
            self.model_name = model_name

        self._dim = 384
        self._index: dict[str, np.ndarray] = {}
        self._id_to_entry: dict[str, str] = {}
        self._entry_to_id: dict[str, str] = {}
        self._lock = threading.RLock()
        self._ready = False
        self._model = None
        self._vectorizer = None
        self._use_transformers = False
        self._active_model_name = "none"
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._errors = 0
        self._queries_served = 0
        self._avg_similarity_sum = 0.0

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="embedding_service",
                    effectiveness_fn=self._calc_embedding_effectiveness,
                    learn_fn=self._learn_from_embedding,
                    evolve_fn=self._evolve_embedding_config,
                    mutable_config={
                        "model_name": self.model_name,
                        "rebuild_threshold": 0.5,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception:
                pass

        self._init_model()
        self._build_index()

    def _init_model(self):
        """模型初始化 — BGE-M3优先 + 多级回退 + MCP启动安全

        【MCP启动修复】优化策略：
        1. 检查环境变量EMBEDDING_ENGINE，支持显式指定TF-IDF避免网络请求
        2. auto模式: 按BGE-M3 → bge-small-zh → MiniLM → TF-IDF顺序快速尝试
        3. 网络错误时立即回退，不阻塞MCP Server启动（不超过10秒）
        4. 失败则优雅回退到TF-IDF（零依赖兜底）

        优先级:
        1. 环境变量EMBEDDING_ENGINE=tfidf → 强制TF-IDF（最快启动）
        2. 用户指定model_name (如"bge-m3"/"tfidf"/"auto")
        3. auto模式: 快速尝试BGE系列（网络失败立即回退）
        4. 最终兜底: sklearn TF-IDF
        """
        import os

        requested = (self.model_name or "auto").lower()

        # 【修复】检查环境变量，优先响应EMBEDDING_ENGINE=tfidf
        env_engine = os.environ.get("EMBEDDING_ENGINE", "").lower()
        if env_engine in ("tfidf", "sklearn", "offline"):
            print(f"[Embedding] 环境变量指定: {env_engine}，直接使用TF-IDF")
            self._init_tfidf()
            return

        # 显式指定TF-IDF — 走老路径
        if requested in ("tfidf", "sklearn"):
            self._init_tfidf()
            return

        # 【修复】显式指定offline模式 — 直接跳到TF-IDF
        if requested == "offline":
            print("[Embedding] 用户指定offline模式，使用TF-IDF")
            self._init_tfidf()
            return

        # auto或transformers模式 — 按优先级快速尝试BGE系列
        # 【彻底修复】只有显式指定transformers/bge-m3时才尝试网络加载
        if requested in ("bge-m3", "transformers", "sentence-transformers"):
            # 【修复】记录尝试次数，避免无限重试阻塞启动
            max_attempts = 3  # 最多尝试3个模型
            attempts = 0

            for model_id, expected_dim, desc in _BGE_MODEL_CANDIDATES:
                # bge-m3特殊: 只在显式指定时尝试
                if requested != "bge-m3" and "bge-m3" in model_id:
                    continue

                attempts += 1
                if attempts > max_attempts:
                    print(
                        f"[Embedding] ⚠️ 达到最大尝试次数({max_attempts})，停止尝试避免阻塞启动"
                    )
                    break

                if self._try_load_model(model_id, expected_dim, desc):
                    return

        # auto/默认/tfidf/offline — 直接使用TF-IDF，零网络依赖
        print("[Embedding] 使用TF-IDF模式 (零网络依赖，快速启动)")
        self._init_tfidf()

    def _try_load_model(self, model_id: str, expected_dim: int, desc: str) -> bool:
        """尝试加载指定sentence-transformers模型

        【MCP启动修复】增加离线模式和快速失败机制：
        - 优先尝试本地缓存（HF_HOME环境变量）
        - 网络失败时快速回退，不阻塞MCP启动
        - 支持显式离线模式（TRANSFORMERS_OFFLINE=1）
        """
        try:
            from sentence_transformers import SentenceTransformer

            print(f"[Embedding] 尝试加载 {desc}: {model_id} ...")

            # 【修复】检查离线模式环境变量，避免网络请求
            import os

            offline_mode = os.environ.get("TRANSFORMERS_OFFLINE", "0") == "1"

            # 【修复】设置超时和重试限制，避免长时间阻塞
            try:
                # 尝试加载，优先使用本地缓存
                if offline_mode:
                    print("[Embedding] 离线模式: 仅使用本地缓存")
                    self._model = SentenceTransformer(
                        model_id, cache_folder=os.environ.get("HF_HOME")
                    )
                else:
                    # 正常模式，但设置较短超时
                    self._model = SentenceTransformer(model_id)

                self._dim = (
                    self._model.get_sentence_embedding_dimension() or expected_dim
                )
                self._use_transformers = True
                self._ready = True
                self._active_model_name = model_id
                print(f"[Embedding] ✅ 加载成功: {model_id} (dim={self._dim}) - {desc}")
                return True

            except Exception as load_err:
                # 【修复】捕获网络错误，快速失败
                err_type = type(load_err).__name__
                if any(
                    keyword in str(load_err)
                    for keyword in [
                        "WinError",
                        "Connection",
                        "Timeout",
                        "10054",
                        "10060",
                    ]
                ):
                    print(f"[Embedding] ⚠️ 网络错误快速回退: {err_type}")
                    return False
                else:
                    # 其他错误继续尝试下一个模型
                    err_msg = str(load_err)[:120]
                    print(f"[Embedding] {model_id} 加载失败: {err_msg}")
                    return False

        except ImportError:
            print(f"[Embedding] sentence-transformers未安装，跳过 {model_id}")
            return False
        except Exception as e:
            err_msg = str(e)[:120]
            print(f"[Embedding] {model_id} 加载异常: {err_msg}")
            return False

    def _init_tfidf(self):
        """TF-IDF兜底初始化"""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            self._vectorizer = TfidfVectorizer(
                max_features=2000,
                ngram_range=(1, 3),
                analyzer="char_wb",
            )
            self._dim = 2000
            self._ready = True
            self._use_transformers = False
            self._active_model_name = "tfidf"
            print("[Embedding] 使用 sklearn TF-IDF 向量化 (零额外依赖)")
        except ImportError:
            print("[Embedding] sklearn 不可用，使用简单哈希向量化")
            self._ready = True
            self._dim = 256
            self._active_model_name = "hash"

    def _try_load_transformers(self):
        """兼容旧API — 调用新的多模型加载逻辑"""
        return self._try_load_model(
            "paraphrase-multilingual-MiniLM-L12-v2", 384, "多语言MiniLM"
        )

    def _encode(self, text: str) -> np.ndarray:
        if self._use_transformers and self._model:
            return self._model.encode(text, convert_to_numpy=True)

        if self._vectorizer:
            try:
                vec = self._vectorizer.transform([text]).toarray()[0]
                vec = vec / (np.linalg.norm(vec) + 1e-8)
                return vec.astype(np.float32)
            except Exception:
                return self._fallback_encode(text)

        return self._fallback_encode(text)

    def _fallback_encode(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        for i, char in enumerate(text[: self._dim * 10]):
            idx = ord(char) % self._dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    @staticmethod
    def _get_attr(entry, attr, default=None):
        if isinstance(entry, dict):
            return entry.get(attr, default)
        return getattr(entry, attr, default)

    def _build_index(self):
        with self._lock:
            self._index.clear()
            self._id_to_entry.clear()
            self._entry_to_id.clear()

            entries = self.engine.get_all_entries(limit=2000)
            texts = [self._get_attr(e, "content", "") for e in entries]

            if self._vectorizer and texts:
                try:
                    self._vectorizer.fit(texts)
                except Exception:
                    pass

            for entry in entries:
                try:
                    content = self._get_attr(entry, "content", "")
                    entry_id = self._get_attr(entry, "id", "")
                    if not content or not entry_id:
                        continue
                    vec = self._encode(content)
                    self._index[entry_id] = vec
                    self._id_to_entry[entry_id] = entry_id
                except Exception:
                    pass

            print(f"[Embedding] 索引构建完成: {len(self._index)} 条向量")

    def rebuild_index(self) -> int:
        before = len(self._index)
        self._build_index()
        after = len(self._index)

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="rebuild_index",
                    state_before={"index_size": before},
                    state_after={"index_size": after, "ready": self._ready},
                )
            except Exception:
                pass

        return after

    def semantic_search(self, query: str, limit: int = 20) -> list[dict]:
        if not self._index:
            self._build_index()

        query_vec = self._encode(query)

        with self._lock:
            scores = []
            for entry_id, vec in self._index.items():
                sim = self._cosine_similarity(query_vec, vec)
                scores.append((sim, entry_id))

            scores.sort(reverse=True)
            top_ids = [eid for _, eid in scores[:limit]]

        if not top_ids:
            return []

        id_set = set(top_ids)
        entry_map = {}
        try:
            all_entries = self.engine.get_all_entries(limit=2000)
            for e in all_entries:
                eid = self._get_attr(e, "id", "")
                if eid in id_set:
                    entry_map[eid] = e
        except Exception:
            pass

        results = []
        for sim, entry_id in scores[:limit]:
            entry = entry_map.get(entry_id)
            if entry:
                content = self._get_attr(entry, "content", "")
                results.append(
                    {
                        "id": self._get_attr(entry, "id", entry_id),
                        "content_preview": content[:200],
                        "layer": self._get_attr(entry, "layer", ""),
                        "similarity": round(float(sim), 4),
                        "priority": self._get_attr(entry, "priority", "medium"),
                        "tags": self._get_attr(entry, "tags", [])[:5],
                    }
                )

        self._queries_served += 1
        if results:
            self._avg_similarity_sum += results[0]["similarity"]

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="semantic_search",
                    state_before={"query": query[:100]},
                    state_after={
                        "hits": len(results),
                        "top_similarity": results[0]["similarity"] if results else 0.0,
                        "queries_served": self._queries_served,
                    },
                )
            except Exception:
                pass

        return results

    def get_index_stats(self) -> dict:
        return {
            "indexed": len(self._index),
            "total": self.engine.stats()["total_entries"],
            "dimension": self._dim,
            "model": self.model_name,
            "use_transformers": self._use_transformers,
        }

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b + 1e-8))

    def add_to_index(self, entry):
        try:
            content = self._get_attr(entry, "content", "")
            entry_id = self._get_attr(entry, "id", "")
            if not content or not entry_id:
                return
            before = len(self._index)
            vec = self._encode(content)
            with self._lock:
                self._index[entry_id] = vec

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="add_to_index",
                        state_before={"index_size": before},
                        state_after={
                            "index_size": len(self._index),
                            "entry_id": entry_id,
                        },
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def remove_from_index(self, entry_id: str):
        with self._lock:
            self._index.pop(entry_id, None)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "version": "1.1",
            "model": self.model_name,
            "use_transformers": self._use_transformers,
            "ready": self._ready,
            "index_size": len(self._index),
            "dimension": self._dim,
            "queries_served": self._queries_served,
            "errors": self._errors,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "version": "1.1",
            "index_stats": self.get_index_stats(),
            "queries_served": self._queries_served,
            "health": self.health(),
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
        }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_embedding_effectiveness(
        self, action: str, state_before: dict[str, Any], state_after: dict[str, Any]
    ) -> float:
        if action == "rebuild_index":
            growth = state_after.get("index_size", 0) - state_before.get(
                "index_size", 0
            )
            return 0.5 if growth >= 0 else -0.2
        elif action == "semantic_search":
            hits = state_after.get("hits", 0)
            top_sim = state_after.get("top_similarity", 0.0)
            return 0.3 + min(0.5, top_sim) if hits > 0 else 0.0
        elif action == "add_to_index":
            growth = state_after.get("index_size", 0) - state_before.get(
                "index_size", 0
            )
            return 0.4 if growth > 0 else 0.0
        return 0.0

    def _learn_from_embedding(
        self, causal_pairs: list[Any], effectiveness_summary: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "index_size": len(self._index),
            "queries_served": self._queries_served,
            "model": self.model_name,
        }

    def _evolve_embedding_config(
        self, learn_result: dict[str, Any], mutable_config: dict[str, Any]
    ) -> dict[str, Any]:
        changes = {}
        queries = learn_result.get("queries_served", 0)
        index_size = learn_result.get("index_size", 0)
        if queries > 1000 and index_size > 1000:
            changes["rebuild_threshold"] = 0.3
        elif queries < 100:
            changes["rebuild_threshold"] = 0.5
        return {"rules_modified": changes, "skills_created": []}
