"""
tests/test_core/test_dependency_container.py - 依赖注入容器单元测试
"""
import pytest
from core.shared.dependency_container import DependencyContainer, TianjiContainer, ServiceLifetime


class TestDependencyContainer:
    """DependencyContainer依赖注入容器测试"""
    
    @pytest.fixture
    def container(self):
        """创建容器实例"""
        return DependencyContainer()
    
    def test_container_creation(self, container):
        """测试容器创建"""
        assert container is not None
        assert isinstance(container, DependencyContainer)
    
    def test_register_singleton_instance(self, container):
        """测试注册单例实例"""
        class TestService:
            def __init__(self, value):
                self.value = value
        
        service = TestService(42)
        container.register_singleton(TestService, instance=service)
        
        resolved = container.resolve(TestService)
        assert resolved is service
        assert resolved.value == 42
    
    def test_register_singleton_factory(self, container):
        """测试注册单例工厂"""
        class TestService:
            def __init__(self, value):
                self.value = value
        
        container.register_singleton(
            TestService,
            factory=lambda: TestService(100)
        )
        
        resolved1 = container.resolve(TestService)
        resolved2 = container.resolve(TestService)
        
        assert resolved1.value == 100
        assert resolved1 is resolved2
    
    def test_register_transient(self, container):
        """测试注册瞬态服务"""
        class TransientService:
            counter = 0
            
            def __init__(self):
                TransientService.counter += 1
                self.id = TransientService.counter
        
        container.register_transient(TransientService)
        
        instance1 = container.resolve(TransientService)
        instance2 = container.resolve(TransientService)
        
        assert instance1 is not instance2
        assert instance1.id == 1
        assert instance2.id == 2
    
    def test_try_resolve_existing(self, container):
        """测试尝试解析已存在服务"""
        class Service:
            pass
        
        container.register_singleton(Service, instance=Service())
        
        resolved = container.try_resolve(Service)
        assert resolved is not None
        assert isinstance(resolved, Service)
    
    def test_try_resolve_non_existing(self, container):
        """测试尝试解析不存在服务"""
        class NonExistingService:
            pass
        
        resolved = container.try_resolve(NonExistingService)
        assert resolved is None
    
    def test_resolve_non_existing_raises(self, container):
        """测试解析不存在服务抛出异常"""
        class NonExistingService:
            pass
        
        with pytest.raises(Exception):
            container.resolve(NonExistingService)
    
    def test_clear(self, container):
        """测试清空容器"""
        class Service:
            pass
        
        container.register_singleton(Service, instance=Service())
        container.clear()
        
        assert container.try_resolve(Service) is None


class TestServiceLifetime:
    """ServiceLifetime枚举测试"""
    
    def test_lifetime_values(self):
        """测试生命周期枚举值"""
        assert ServiceLifetime.SINGLETON.value == "singleton"
        assert ServiceLifetime.TRANSIENT.value == "transient"
        assert ServiceLifetime.SCOPED.value == "scoped"


class TestTianjiContainer:
    """TianjiContainer全局容器测试"""
    
    def test_get_instance(self):
        """测试获取全局实例"""
        container = TianjiContainer.get_instance()
        assert container is not None
        assert isinstance(container, DependencyContainer)
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        container1 = TianjiContainer.get_instance()
        container2 = TianjiContainer.get_instance()
        
        assert container1 is container2
    
    def test_reset(self):
        """测试重置容器"""
        container1 = TianjiContainer.get_instance()
        TianjiContainer.reset()
        container2 = TianjiContainer.get_instance()
        
        assert container1 is not container2
