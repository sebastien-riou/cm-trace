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

__attribute__((optimize("align-functions=4"),noinline)) uint64_t loop64(uint64_t a, uint64_t n){
	for(uint64_t i = 0; i < n; i++){
		a = (a<<11) ^ (a<<13) ^ (a>>17);
	}
	return a;
}
__attribute__((optimize("align-functions=4"),noinline)) void test_loop64_core(){
	sink64 = loop64(vbuf64[0],vbuf64[1]);
}
__attribute__((optimize("align-functions=4"))) void test_loop64_4(){
	vbuf64[0] = 0x12345678;
	vbuf64[1] = 4;
	test_loop64_core();
}
__attribute__((optimize("align-functions=4"))) void test_loop64_32(){
	vbuf64[0] = 0x12345678;
	vbuf64[1] = 32;
	test_loop64_core();
}
__attribute__((optimize("align-functions=4"))) void test_loop64_256(){
	vbuf64[0] = 0x12345678;
	vbuf64[1] = 256;
	test_loop64_core();
}
__attribute__((optimize("align-functions=4"))) void test_loop64_100k(){
	vbuf64[0] = 0x12345678;
	vbuf64[1] = 100*1024;
	test_loop64_core();
}
void include_test_functions(){
	sink64 = 	(uintptr_t)test_umul64_16_16+
				(uintptr_t)test_umul64_32_16+
				(uintptr_t)test_umul64_32_32+
				(uintptr_t)test_loop64_4+
				(uintptr_t)test_loop64_32+
				(uintptr_t)test_loop64_256+
				(uintptr_t)test_loop64_100k;
}