#!/usr/bin/python3

# A not very good KVM client / virtual machine manager written in python.
# Based heavily on the excellent https://lwn.net/Articles/658511/.
# Development was assisted by Claude Sonnet 4.5, and US Intellectual
# Property law.


import ctypes
import fcntl
import mmap
import sys

from displayhelpers import *
from exitcodes import *
from ioctls import *
from structs import *


# A single 4kb page
MEM_SIZE = 0x1000


def main():
    # Open the KVM device file. This gives us a top level reference to the
    # KVM API which we can then make global calls against.
    with open('/dev/kvm', 'rb+', buffering=0) as kvm:
        try:
            # Check that the API is a supported version. This should
            # basically never fail on a modern kernel.
            api_version = fcntl.ioctl(kvm, KVM_GET_API_VERSION)
            print(f'KVM API version: {api_version}')
            if api_version != 12:
                print(f'KVM API version {api_version} was unexpected')
                sys.exit(1)
        except OSError as e:
            print(
                f'Failed to lookup KVM API version: {e.errno} - {e.strerror}'
                )
            sys.exit(1)

        # Create a VM file descriptor. This is the "object" which tracks the
        # virtual machine we are creating.
        print()
        try:
            vm = fcntl.ioctl(kvm, KVM_CREATE_VM)
            print(f'VM file descriptor: {vm}')
        except OSError as e:
            print(f'Failed to create a VM: {e.errno} - {e.strerror}')
            sys.exit(1)

        # mmap memory for the VM to use. Sonnet 4.5 alleges that we need to
        # use mmap here instead of just allocating a largeish byte array in
        # native python for a few reasons: the allocation needs to be
        # page-aligned; mmap'ed memory can be zero-copied into the virtual
        # machine, a python array cannot; MAP_SHARED means our python process
        # can inspect the state of the virtual machine's memory; python
        # memory allocations are not at a stable location -- python might
        # rearrange things. So yeah, those seem like reasons to me.
        mem = mmap.mmap(
            -1,
            MEM_SIZE,
            prot=mmap.PROT_READ | mmap.PROT_WRITE,
            flags=mmap.MAP_SHARED | mmap.MAP_ANONYMOUS,
            offset=0
        )
        mem_buf = (ctypes.c_char * len(mem)).from_buffer(mem)
        mem_addr = ctypes.addressof(mem_buf)
        print(f'VM memory page is at 0x{mem_addr:x}')

        # This is the data structure we're going to pass to the kernel to
        # tell if about all this memory we have allocated.
        region_s = kvm_userspace_memory_region_t()
        region_s.slot = 0
        region_s.flags = 0
        region_s.guest_phys_addr = 0
        region_s.memory_size = MEM_SIZE
        region_s.userspace_addr = mem_addr

        try:
            # This dance gives us the address of the data structure, which is
            # what the kernel is expecting.
            region_bytes = ctypes.string_at(
                ctypes.addressof(region_s), ctypes.sizeof(region_s))
            fcntl.ioctl(vm, KVM_SET_USER_MEMORY_REGION, region_bytes)
        except OSError as e:
            print(f'Failed to map memory into VM: {e.errno} - {e.strerror}')
            sys.exit(1)

        # Add a vCPU to the VM. The vCPU is another object we can do things
        # to later.
        try:
            # The zero here is the index of the vCPU, this one being of
            # course our first.
            vcpu = fcntl.ioctl(vm, KVM_CREATE_VCPU, 0)
            print(f'vCPU file descriptor: {vcpu}')
        except OSError as e:
            print(f'Failed to create a vCPU: {e.errno} - {e.strerror}')
            sys.exit(1)

        # mmap the CPU state structure from the kernel to userspace. We need
        # to lookup the size of the structure, and the LWN article notes:
        # "Note that the mmap size typically exceeds that of the kvm_run
        # structure, as the kernel will also use that space to store other
        # transient structures that kvm_run may point to".
        try:
            kvm_run_size = fcntl.ioctl(kvm, KVM_GET_VCPU_MMAP_SIZE)
        except OSError as e:
            print(
                f'Failed to lookup kvm_run struct size: {e.errno} - '
                f'{e.strerror}'
            )
            sys.exit(1)

        print()
        print(f'The KVM run structure is {kvm_run_size} bytes')

        kvm_run = mmap.mmap(
            vcpu,
            kvm_run_size,
            prot=mmap.PROT_READ | mmap.PROT_WRITE,
            flags=mmap.MAP_SHARED,
            offset=0
        )
        kvm_run_s = kvm_run_t.from_buffer(kvm_run)
        kvm_run_addr = ctypes.addressof(kvm_run_s)
        print(f'vCPU KVM run struture is at 0x{kvm_run_addr:x}')
        print()
        print(pretty_print_struct(kvm_run_s))
        print()

        # Read the initial state of the vCPU special registers
        sregs = kvm_sregs_t()
        fcntl.ioctl(vcpu, KVM_GET_SREGS, sregs)
        print('Initial vCPU special registers state')
        print()
        print(pretty_print_sregs(sregs))
        print()

        # Setup sregs per the LWN article. cs by default points to the
        # reset vector at 16 bytes below the top of memory. We want to start
        # at the begining of memory instead.
        sregs.cs.base = 0
        sregs.cs.selector = 0
        fcntl.ioctl(vcpu, KVM_SET_SREGS, sregs)

        # Read back to validate the change
        sregs = kvm_sregs_t()
        fcntl.ioctl(vcpu, KVM_GET_SREGS, sregs)
        print('CS updated vCPU special registers state')
        print()
        print(pretty_print_sregs(sregs))
        print()

        # Read the initial state of the vCPU standard registers
        regs = kvm_regs_t()
        fcntl.ioctl(vcpu, KVM_GET_REGS, regs)
        print('Initial vCPU standard registers state')
        print()
        print(pretty_print_struct(regs))
        print()

        # Setup regs per the LWN article. We set the instruction pointer (IP)
        # to 0x0 relative to the CS at 0, set RAX and RBX to 2 each as our
        # initial inputs to our program, and set the flags to 0x2 as this is
        # documented as the start state of the CPU. Note that the LWN article
        # originally had the code at 0x1000, which is super confusing because
        # that's outside the 4kb of memory we actually allocated.
        regs.rip = 0x0
        regs.rax = 2
        regs.rbx = 2
        regs.rflags = 0x2
        fcntl.ioctl(vcpu, KVM_SET_REGS, regs)

        # Read back to validate the change
        regs = kvm_regs_t()
        fcntl.ioctl(vcpu, KVM_GET_REGS, regs)
        print('Updated vCPU standard registers state')
        print()
        print(pretty_print_struct(regs))
        print()

        # Set the memory to contain our simple demo program, which is from
        # the LWN article again. Its important to note that the memory we
        # mapped earlier is accessible to _both_ this userspace program and
        # the vCPU, so we can totally poke around in it if we want.
        program = bytes([
            0xba,       # mov $0x3f8, %dx
            0xf8,
            0x03,
            0x00,       # add %bl, %al
            0xd8,
            0x04,       # add $'0', %al
            ord('0'),
            0xee,       # out %al, (%dx)
            0xb0,       # mov $'\n', %al
            ord('\n'),
            0xee,       # out %al, (%dx)
            0xf4,       # hlt
        ])
        mem[0:len(program)] = program

        # And we now enter into the VMM main loop, which is where we sit for
        # the lifetime of the virtual machine. Each return from the ioctl is
        # called a "VM Exit" and indicates that a protection violation in
        # the vCPU has signalled a request for us to do something.
        while True:
            fcntl.ioctl(vcpu, KVM_RUN)
            kvm_run_s = kvm_run_t.from_buffer(kvm_run)
            exit_reason = VM_EXIT_CODES[kvm_run_s.exit_reason]
            print(f'VM exit: {exit_reason}')

            match exit_reason:
                case 'KVM_EXIT_HLT':
                    print('Program complete (halted)')
                    sys.exit(0)

                case 'KVM_EXIT_IO':
                    print('I really should implement this...')
                    sys.exit(2)

                case 'KVM_EXIT_SHUTDOWN':
                    print('VM shutdown')
                    sys.exit(0)

                case 'KVM_EXIT_INTERNAL_ERROR':
                    print('Internal errors are probably bad?')
                    sys.exit(1)

                case _:
                    print(f'Unhandled VM exit: {exit_reason}')
                    break


if __name__ == '__main__':
    main()