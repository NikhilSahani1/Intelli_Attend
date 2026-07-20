"""
Configuration package
"""
from config.development import DevelopmentConfig
from config.production import ProductionConfig

__all__ = ['DevelopmentConfig', 'ProductionConfig']