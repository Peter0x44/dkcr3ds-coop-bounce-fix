    .syntax unified
    .arm
    .fpu vfpv2
    @ r5 = creature. Return r0 != 0 if the creature is alive OR its corpse timer is still running.
    ldrb    r0, [r5, #0x22d]
    cmp     r0, #0
    bne     1f
    vldr    s0, [r5, #0x30c]
    vcmpe.f32 s0, #0
    vmrs    APSR_nzcv, fpscr
    movgt   r0, #1
1:  nop     @ build_patches.py fills in: b 0x2ECDE0
