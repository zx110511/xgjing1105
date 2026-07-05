import sys
sys.path.insert(0, r'd:\元初系统\天机v9.1')

mods = [
    'core.config', 'core.engine', 'core.models', 'core.quality_gate',
    'core.skill_registry', 'core.learning_loop', 'core.evolution_engine',
    'core.evolution_loop', 'core.deepseek_driver', 'core.async_bridge',
    'core.workflow_engine', 'core.message_gateway',
    'core.intelligent_scheduler', 'core.enforcement_hook',
    'core.agent_orchestrator', 'core.hybrid_engine', 'core.sqlite_store',
    'core.llm_bridge', 'core.router', 'core.namespace_manager',
    'indexing.embeddings', 'indexing.cognition', 'indexing.summarizer',
    'indexing.knowledge_graph', 'llm_integration', 'llm_integration.client',
    'llm_integration.decision_engine', 'llm_integration.cache',
    'adapters.base', 'adapters.ai_platform_adapters',
    'active_memory.protocol', 'server.deps',
]

results = []
for m in mods:
    try:
        __import__(m)
        results.append(f'OK  {m}')
    except Exception as e:
        results.append(f'FAIL {m}: {str(e)[:100]}')

print()
for r in results:
    print(r)

ok_count = sum(1 for r in results if r.startswith('OK'))
fail_count = sum(1 for r in results if r.startswith('FAIL'))
print(f'\nTotal: {ok_count} OK / {fail_count} FAIL / {len(results)} modules')
