#!/usr/bin/python3

# A not very good KVM client / virtual machine manager written in python.
# Based heavily on the excellent https://lwn.net/Articles/658511/.
# Development was assisted by Claude Sonnet 4.5, and US Intellectual
# Property law.


import ctypes
import fcntl
import mmap
import os
import struct
import sys

from prettytable import PrettyTable

import _ioctls


# A single 4kb page
MEM_SIZE = 0x1000


# Set up KVM memory region structure. I hadn't seen ctypes.Structure
# before, and it makes me wonder if my previous extensive use of
# struct.pack() and struct.unpack() was a poor life choice.
#
# https://docs.kernel.org/virt/kvm/api.html#kvm-set-user-memory-region
# https://github.com/torvalds/linux/blob/master/include/uapi/linux/kvm.h#L25

class kvm_userspace_memory_region_t(ctypes.Structure):
    _fields_ = [
        ("slot", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("guest_phys_addr", ctypes.c_uint64),
        ("memory_size", ctypes.c_uint64),
        ("userspace_addr", ctypes.c_uint64),
    ]


# Similarly, we also need a pythonic kvm_run structure.
#
# https://docs.kernel.org/virt/kvm/api.html#kvm-set-user-memory-region
# https://github.com/torvalds/linux/blob/master/include/uapi/linux/kvm.h#L210

class kvm_run_t(ctypes.Structure):
    _fields_ = [
        # Input
        ('request_interrupt_window', ctypes.c_uint8),
        ('immediate_exit', ctypes.c_uint8),
        ('_padding1', ctypes.c_uint8 * 6),

        # Output
        ('exit_reason', ctypes.c_uint32),
        ('ready_for_interrupt_injection', ctypes.c_uint8),
        ('if_flag', ctypes.c_uint8),
        ('flags', ctypes.c_uint8 * 2),

        # in (pre_kvm_run), out (post_kvm_run)
        ('cr8', ctypes.c_uint64),
        ('apic_base', ctypes.c_uint64),

        # The exit_reasons part of the struct is... like totally complicated.
        # https://github.com/torvalds/linux/blob/master/include/uapi/linux/kvm.h#L231
    ]


# vCPU special registers, including nested structures.
#
# https://docs.kernel.org/virt/kvm/api.html#kvm-get-sregs
# https://github.com/torvalds/linux/blob/master/arch/x86/include/uapi/asm/kvm.h#L150

class kvm_segment_t(ctypes.Structure):
    _fields_ = [
        ('base', ctypes.c_uint64),
        ('limit', ctypes.c_uint32),
        ('selector', ctypes.c_uint16),
        ('type', ctypes.c_uint8),
        ('present', ctypes.c_uint8),
        ('dpl', ctypes.c_uint8),
        ('db', ctypes.c_uint8),
        ('s', ctypes.c_uint8),
        ('l', ctypes.c_uint8),
        ('g', ctypes.c_uint8),
        ('avl', ctypes.c_uint8),
        ('unusable', ctypes.c_uint8),
        ('padding', ctypes.c_uint8),
    ]

class kvm_dtable_t(ctypes.Structure):
    _fields_ = [
        ('base', ctypes.c_uint64),
        ('limit', ctypes.c_uint16),
        ('padding', ctypes.c_uint16 * 3),
    ]

# KVM_NR_INTERRUPTS is typically 256
KVM_NR_INTERRUPTS = 256

class kvm_sregs_t(ctypes.Structure):
    _fields_ = [
        ('cs', kvm_segment_t),
        ('ds', kvm_segment_t),
        ('es', kvm_segment_t),
        ('fs', kvm_segment_t),
        ('gs', kvm_segment_t),
        ('ss', kvm_segment_t),
        ('tr', kvm_segment_t),
        ('ldt', kvm_segment_t),
        ('gdt', kvm_dtable_t),
        ('idt', kvm_dtable_t),
        ('cr0', ctypes.c_uint64),
        ('cr2', ctypes.c_uint64),
        ('cr3', ctypes.c_uint64),
        ('cr4', ctypes.c_uint64),
        ('cr8', ctypes.c_uint64),
        ('efer', ctypes.c_uint64),
        ('apic_base', ctypes.c_uint64),
        (
            'interrupt_bitmap',
            ctypes.c_uint64 * ((KVM_NR_INTERRUPTS + 63) // 64)
        ),
    ]


# Helpers
def pretty_print_struct(s):
    # This relies on the magic of ctypes.Structure.
    table = PrettyTable()
    table.field_names = ['Name', 'Type', 'Value']
    table.align = 'l'

    for field_name, field_type in s._fields_:
        if field_name.startswith('_'):
            continue

        row = [field_name, field_type.__name__]
        value = getattr(s, field_name)
        if isinstance(value, int):
            row.append(f'      0x{value:x} ({value})')
        elif hasattr(field_type, '_length_'):
            array = []
            for i, item in enumerate(value):
                array.append(f'[{i:2}]: 0x{item:x} ({item})')
            row.append('\n'.join(array))
        elif hasattr(field_type, '_fields_'):
            row.append(pretty_print_struct(value))
        else:
            row.append(f'      {value}')

        table.add_row(row)

    return table.get_string()


def main():
    # Open the KVM device file. This gives us a top level reference to the
    # KVM API which we can then make global calls against.
    with open('/dev/kvm', 'rb+', buffering=0) as kvm:
        try:
            # Check that the API is a supported version. This should
            # basically never fail on a modern kernel.
            api_version = fcntl.ioctl(kvm, _ioctls.KVM_GET_API_VERSION)
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
            vm = fcntl.ioctl(kvm, _ioctls.KVM_CREATE_VM)
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
            fcntl.ioctl(vm, _ioctls.KVM_SET_USER_MEMORY_REGION, region_bytes)
        except OSError as e:
            print(f'Failed to map memory into VM: {e.errno} - {e.strerror}')
            sys.exit(1)

        # Add a vCPU to the VM. The vCPU is another object we can do things
        # to later.
        try:
            # The zero here is the index of the vCPU, this one being of
            # course our first.
            vcpu = fcntl.ioctl(vm, _ioctls.KVM_CREATE_VCPU, 0)
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
            kvm_run_size = fcntl.ioctl(kvm, _ioctls.KVM_GET_VCPU_MMAP_SIZE)
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

        # Read and then update the vCPU special registers
        sregs = kvm_sregs_t()
        fcntl.ioctl(vcpu, _ioctls.KVM_GET_SREGS, sregs)
        print('Initial vCPU special registers state')
        print()
        print(pretty_print_struct(sregs))


if __name__ == '__main__':
    main()