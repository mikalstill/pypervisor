import ctypes


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


# Similarly, we also need a pythonic kvm_run structure including nested
# structures.
#
# https://docs.kernel.org/virt/kvm/api.html#kvm-set-user-memory-region
# https://github.com/torvalds/linux/blob/master/include/uapi/linux/kvm.h#L210


class kvm_run_io_t(ctypes.Structure):
    _fields_ = [
        ('direction', ctypes.c_uint8),
        ('size', ctypes.c_uint8),
        ('port', ctypes.c_uint16),
        ('count', ctypes.c_uint32),
        ('data_offset', ctypes.c_uint64),
    ]


class kvm_exit_reason_t(ctypes.Union):
    _fields_ = [
        ('io', kvm_run_io_t)
    ]


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
        ('exit_reasons', kvm_exit_reason_t),
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


# vCPU standard registers, including nested structures.
#
# https://docs.kernel.org/virt/kvm/api.html#kvm-get-regs
# https://github.com/torvalds/linux/blob/master/arch/x86/include/uapi/asm/kvm.h#L117
class kvm_regs_t(ctypes.Structure):
    _fields_ = [
        ('rax', ctypes.c_uint64),
        ('rbx', ctypes.c_uint64),
        ('rcx', ctypes.c_uint64),
        ('rdx', ctypes.c_uint64),
        ('rsi', ctypes.c_uint64),
        ('rdi', ctypes.c_uint64),
        ('rsp', ctypes.c_uint64),
        ('rbp', ctypes.c_uint64),
        ('r8', ctypes.c_uint64),
        ('r9', ctypes.c_uint64),
        ('r10', ctypes.c_uint64),
        ('r11', ctypes.c_uint64),
        ('r12', ctypes.c_uint64),
        ('r13', ctypes.c_uint64),
        ('r14', ctypes.c_uint64),
        ('r15', ctypes.c_uint64),
        ('rip', ctypes.c_uint64),
        ('rflags', ctypes.c_uint64),
    ]