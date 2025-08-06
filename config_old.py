import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://dor_pi:]44p7214)S@176.58.117.107/dor_pi'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
