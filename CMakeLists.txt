cmake_minimum_required(VERSION 3.8)
project(usv_rtk_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

install(DIRECTORY udev
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  utilities/check_swepos
  utilities/check_serial
  utilities/gnss_link_monitor
  utilities/ntrip_aux_client
  utilities/ntrip_ros_client
  utilities/merge_sbg_params
  utilities/dual_antenna_attitude_remap
  utilities/sbg_settings
  utilities/sbg_settings_publisher
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES utilities/ntrip_secrets.py
  utilities/attitude_remap.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
