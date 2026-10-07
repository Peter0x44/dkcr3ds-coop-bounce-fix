    .syntax unified
    .arm
    .fpu vfpv2
    @ hooked at 0x2EE644 (behavior collision dispatcher). r4 = creature, r1 = other actor, r8 = contact type.
    @ A dead creature inside its corpse window has no active behavior, so the dispatcher would drop the
    @ contact. Hand it straight to the contact-handler wrapper instead (what a behavior would call).
    ldrb    r0, [r4, #0x22d]
    cmp     r0, #0
    bne     1f
    vldr    s0, [r4, #0x30c]
    vcmpe.f32 s0, #0
    vmrs    APSR_nzcv, fpscr
    ble     1f
    mov     r0, r4
    mov     r2, r8
    mvn     r3, #0
    nop                 @ -> bl 0x22CCC4
    nop                 @ -> b  0x2EE724 (return)
1:  ldrb    r0, [r4, #0x3c]     @ original instruction
    nop                 @ -> b  0x2EE648
