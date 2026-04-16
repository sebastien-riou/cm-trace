set(LIB cmtrace)

add_library(${LIB} STATIC 
        ${CMAKE_CURRENT_SOURCE_DIR}/source/cmtrace.c
        ${CMAKE_CURRENT_SOURCE_DIR}/source/cmtrace_asm.S 
    )

target_include_directories(${LIB}
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../target/${TARGET_CPU}
    ${CMAKE_CURRENT_SOURCE_DIR}/../target/CMSIS/Include
)

# Compiler options
target_compile_options(${LIB} PRIVATE
    ${cpu_PARAMS}
    ${compiler_OPTS}
    -Wall
    -Wextra
    -Wpedantic
    -Wno-unused-parameter
    $<$<COMPILE_LANGUAGE:C>: >
    $<$<COMPILE_LANGUAGE:CXX>:

    # -Wno-volatile
    # -Wold-style-cast
    # -Wuseless-cast
    # -Wsuggest-override
    >
    $<$<COMPILE_LANGUAGE:ASM>:-x assembler-with-cpp -MMD -MP>
    $<$<CONFIG:Debug>:-Og -g3 -ggdb>
    $<$<CONFIG:Release>:-Os -g0>
)

include("${CMAKE_CURRENT_LIST_DIR}/../cmake/git_version.cmake")
add_definitions( -DGIT_VERSION=${GIT_VERSION} )
add_definitions( -DVERSION_TIMESTAMP=${VERSION_TIMESTAMP} )
add_definitions( -DBUILD_TYPE=${CMAKE_BUILD_TYPE})

add_custom_command(
  TARGET cmtrace POST_BUILD
  COMMAND ls -l ${CMAKE_BINARY_DIR}
  COMMAND ls -l $<TARGET_FILE:cmtrace>
  COMMAND ${CMAKE_AR} -x $<TARGET_FILE:cmtrace>
  COMMAND ${CMAKE_OBJDUMP} -D ${OBJDUMP_OPTIONS} *.${CMAKE_AR_O_EXT} > disassembly.asm
)