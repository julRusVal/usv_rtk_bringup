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
  utilities/ntrip_aux_client
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES utilities/ntrip_secrets.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
