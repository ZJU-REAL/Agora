"""Legacy platform integrations, loaded only when explicitly requested."""
__all__ = ["Channel", "Platform"]
def __getattr__(name):
    if name == "Channel":
        from .channel import Channel
        return Channel
    if name == "Platform":
        from .platform import Platform
        return Platform
    raise AttributeError(name)
