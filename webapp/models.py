from . import db

class Config(db.Model):

    __tablename__ = 'config'

    key = db.Column(
        db.String(64),
        primary_key=True
    )
    min = db.Column(
        db.Float,
        index=False,
        unique=True,
        nullable=False
    )
    max = db.Column(
        db.Float,
        index=False,
        unique=True,
        nullable=False
    )    
    value = db.Column(
        db.Float,
        index=False,
        unique=True,
        nullable=False
    )

    def __repr__(self):
        return '<Config key={k} min={min} max={max} value={v}>'.format(k=self.key,min=self.min,max=self.max,v=self.value)
