# Outlook CDP 注册路径只需 cdp_outlook；完整 Ninjemail 管理器可选加载
try:
    from .邮箱注册_manager import 邮箱注册
except ImportError:
    邮箱注册 = None  # type: ignore