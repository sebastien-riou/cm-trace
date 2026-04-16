cmake_minimum_required(VERSION 3.22)

project(cmtrace LANGUAGES C ASM)

#message(WARNING "CMAKE_C_COMPILER is ${CMAKE_C_COMPILER}")
#message(WARNING "CMAKE_AR is ${CMAKE_AR}")

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)

add_subdirectory(libcmtrace)

if(BUILD_TEST)

# Sources
set(sources_SRCS
	${CMAKE_CURRENT_SOURCE_DIR}/test/source/main.c
)

# Include directories
set(include_c_DIRS
	${CMAKE_CURRENT_SOURCE_DIR}/libcmtrace/include
)

# libs
set(link_DIRS
	${CMAKE_CURRENT_BINARY_DIR}/libcmtrace
)

list(APPEND link_LIBS cmtrace)

include("cmake/generic_binary.cmake")

include(CTest)
add_test(NAME cmtrace
					COMMAND cmtrace)

endif(BUILD_TEST)