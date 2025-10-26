#include <linux/kvm.h>
#include <stdio.h>


void main(){
    printf("KVM_GET_API_VERSION = %lu\n", KVM_GET_API_VERSION);
    printf("KVM_CREATE_VM = %lu\n", KVM_CREATE_VM);
    printf("KVM_SET_USER_MEMORY_REGION = %lu\n", KVM_SET_USER_MEMORY_REGION);
    printf("KVM_CREATE_VCPU = %lu\n", KVM_CREATE_VCPU);
    printf("KVM_GET_VCPU_MMAP_SIZE = %lu\n", KVM_GET_VCPU_MMAP_SIZE);
    printf("KVM_GET_SREGS = %lu\n", KVM_GET_SREGS);
    printf("KVM_SET_SREGS = %lu\n", KVM_SET_SREGS);
}