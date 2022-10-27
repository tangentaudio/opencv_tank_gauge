from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_redis import FlaskRedis

db = SQLAlchemy()
r = FlaskRedis()

def init_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object('config.Config')

    db.init_app(app)
    r.init_app(app)
    
    with app.app_context():
        db.create_all()

        from . import routes

        app.jinja_env.globals.update(template_slider=routes.template_slider)
        
        
        return app

