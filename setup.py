from glob import glob
from setuptools import setup

name = 'facial_expression_control'
setup(
    name=name,
    version='0.1.0',
    packages=[name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + name]),
        ('share/' + name, ['package.xml', 'README.md', 'THIRD_PARTY_NOTICES.txt', 'requirements.txt', 'install.sh', 'run.sh', 'check_environment.py']),
        ('share/' + name + '/launch', glob('launch/*.launch.py')),
        ('share/' + name + '/worlds', glob('worlds/*.sdf')),
        ('share/' + name + '/gui', glob('gui/*.config')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='TurtleBot student',
    maintainer_email='student@example.com',
    description='Facial expression recognition and TurtleBot control dashboard',
    license='Apache-2.0',
    entry_points={'console_scripts': ['emotion_pilot = facial_expression_control.app:main']},
)
