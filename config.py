"""Flask configuration."""
from os import environ, path

basedir = path.abspath(path.dirname(__file__))


class Config:
    """Set Flask config variables."""

    FLASK_ENV = 'development'
    TESTING = True

    STATIC_FOLDER = 'static'
    TEMPLATES_FOLDER = 'templates'

    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:////opt/opencv_tank_gauge/db/gauge.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    
