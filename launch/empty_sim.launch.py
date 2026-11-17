"""Standalone obstacle-free Gazebo Fortress simulation for Emotion Pilot."""
import os

from ament_index_python.packages import get_package_share_directory as share
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, Shutdown
from launch.conditions import UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def include(package, filename, **arguments):
    path = os.path.join(share(package), 'launch', filename)
    return IncludeLaunchDescription(PythonLaunchDescriptionSource(path),
                                    launch_arguments=arguments.items())


def generate_launch_description():
    project = share('facial_expression_control')
    world = LaunchConfiguration('world')
    world_file = PathJoinSubstitution([project, 'worlds', [world, '.sdf']])
    model = LaunchConfiguration('model')
    headless = LaunchConfiguration('headless')
    resource_paths = [os.path.dirname(share(package)) for package in
                      ['turtlebot4_description', 'irobot_create_description']]
    resource_paths.append(os.path.join(project, 'worlds'))
    resource_paths.append(os.environ.get('IGN_GAZEBO_RESOURCE_PATH', ''))
    gui_paths = [os.path.join(share(package), 'lib') for package in
                 ['turtlebot4_ignition_gui_plugins', 'irobot_create_ignition_plugins']]
    gui_paths.append(os.environ.get('IGN_GUI_PLUGIN_PATH', ''))
    gui_config = os.path.join(project, 'gui', 'arena.config')
    # Avoid inheriting pip OpenCV Qt plugins into the Gazebo executable.
    gazebo_env = {
        'QT_QPA_PLATFORM_PLUGIN_PATH': '/usr/lib/x86_64-linux-gnu/qt5/plugins',
        'QT_QPA_FONTDIR': '/usr/share/fonts',
        'PYTHONNOUSERSITE': '1',
        'IGN_GAZEBO_RESOURCE_PATH': os.pathsep.join(resource_paths),
        'IGN_GUI_PLUGIN_PATH': os.pathsep.join(gui_paths),
        'IGN_GAZEBO_SYSTEM_PLUGIN_PATH': os.pathsep.join([
            os.environ.get('IGN_GAZEBO_SYSTEM_PLUGIN_PATH', ''),
            os.environ.get('LD_LIBRARY_PATH', ''),
        ]),
    }
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value='standard', choices=['standard', 'lite']),
        DeclareLaunchArgument('headless', default_value='false', choices=['true', 'false']),
        # Tên này dùng cho bridge cảm biến, khác với đường dẫn file world.
        DeclareLaunchArgument('world', default_value='emotion_arena', choices=['emotion_arena']),
        # Khởi động đúng Fortress 6 và giữ môi trường model/plugin đã chuẩn bị.
        ExecuteProcess(
            cmd=['ign', 'gazebo', world_file, '-s', '-r', '-v', '4',
                 '--force-version', '6'],
            additional_env=gazebo_env, output='screen', on_exit=Shutdown()),
        ExecuteProcess(
            cmd=['ign', 'gazebo', '-g', '-v', '4', '--gui-config', gui_config,
                 '--force-version', '6'],
            additional_env=gazebo_env, output='screen',
            condition=UnlessCondition(headless)),
        # Cả chế độ có cửa sổ và headless đều cần đồng hồ mô phỏng.
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='clock_bridge',
             arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock']),
        # Khởi tạo robot và controller; không spawn dock hoặc vật cản.
        # Giữ tham số spawn ở phạm vi ngoài vì callback khởi động controller
        # còn dùng namespace sau khi nhóm spawn đã chạy xong.
        include('facial_expression_control', 'spawn_robot.launch.py',
                world=world, model=model, namespace='',
                use_sim_time='true', rviz='false', slam='false',
                localization='false', nav2='false', x='0.0', y='0.0', z='0.0', yaw='0.0'),
    ])
