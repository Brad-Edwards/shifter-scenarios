.section .text
.global _start

.code64
_start:
    lea decoder_input(%rip), %rsi
    mov $decoder_input_end-decoder_input, %ecx
    mov $0x6d2b79f5, %eax
decoder64:
    movzbl (%rsi), %edx
    xor %edx, %eax
    rol $5, %eax
    add $0x9e3779b9, %eax
    inc %rsi
    dec %ecx
    jnz decoder64
    mov %eax, rolling_result(%rip)
    jmp long_return

mixed_mode_entry:
    lea compat_stack_top(%rip), %rsp
    lea decoder_input(%rip), %rsi
    mov $decoder_input_end-decoder_input, %ecx
    mov $0x6d2b79f5, %eax
    lea compat_entry(%rip), %rdx
    pushq $0x23
    pushq %rdx
    lretq

.code32
compat_entry:
    movzbl (%esi), %edx
    xor %edx, %eax
    roll $5, %eax
    add $0x9e3779b9, %eax
    inc %esi
    dec %ecx
    jnz compat_entry
    mov %eax, rolling_result
    pushl $0x33
    pushl $long_return
    lret

.code64
long_return:
    mov rolling_result(%rip), %eax
    mov %rax, %rcx
    movabs $0x100000001b3, %rdx
    imul %rdx, %rcx
    movabs $0x243f6a8885a308d3, %rax
    xor %rcx, %rax
    rol $9, %rax
    xor rolling_result(%rip), %rax
    mov %rax, verifier_result(%rip)

    mov $1, %eax
    mov $1, %edi
    lea verifier_result(%rip), %rsi
    mov $8, %edx
    syscall

    mov $60, %eax
    xor %edi, %edi
    syscall

.section .rodata
decoder_input:
    .ascii "MIG-OG2-R19-R21"
decoder_input_end:

.section .bss
.align 16
rolling_result:
    .skip 8
verifier_result:
    .skip 8
compat_stack:
    .skip 4096
compat_stack_top:

.section .note.GNU-stack,"",@progbits
