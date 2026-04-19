#include <stdint.h>
__attribute__((optimize("align-functions=4"),noinline)) uint64_t umul64(uint64_t a, uint64_t b){
	return a*b;
}

volatile uint64_t vbuf64[2] = {0};
volatile uint64_t sink64;
__attribute__((optimize("align-functions=4"),noinline)) void test_umul64_core(){
	sink64 = umul64(vbuf64[0],vbuf64[1]);
}
__attribute__((optimize("align-functions=4"))) void test_umul64_16_16(){
	vbuf64[0] = 0xFFFF;
	vbuf64[1] = 0xFFFF;
	test_umul64_core();
}
__attribute__((optimize("align-functions=4"))) void test_umul64_32_16(){
	vbuf64[0] = 0xFFFFFFFF;
	vbuf64[1] = 0xFFFF;
	test_umul64_core();
}
__attribute__((optimize("align-functions=4"))) void test_umul64_32_32(){
	vbuf64[0] = 0xFFFFFFFF;
	vbuf64[1] = 0xFFFFFFFF;
	test_umul64_core();
}
