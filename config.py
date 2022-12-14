"""Flask configuration."""
from os import environ, path

basedir = path.abspath(path.dirname(__file__))


class Config:
    """Set Flask config variables."""

    FLASK_ENV = 'development'
    TESTING = True

    STATIC_FOLDER = 'static'
    TEMPLATES_FOLDER = 'templates'

    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:////home/gauge/opencv_tank_gauge/db/gauge.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = 'SuperSecret'
    
