# Empty-column vapor transport guard

The installed SNOWPACK 3.7.0 binary crashes in the raw TKG4 run on
2019-10-07 and the raw DG1 run in early October 2019, after `compSurfaceSublimation` removes the final snow element.
GDB shows `nE = 0`, an empty `Edata` vector, and a segmentation fault in
`VapourTransport::LayerToLayer` at `VapourTransport.cc:217` (or the inlined
vector accessor).

The batch runner uses `empty_snow_vapour_guard.gdb` for those two runs. The guard
returns from `LayerToLayer` immediately after surface sublimation only when
there are no remaining elements. It retains the surface-sublimation work and
skips the invalid subsequent layer-to-layer transfer. It does not disable
sublimation, change input data, alter the physical parameters, or modify the
installed executable/library. All calls with remaining elements continue.

This is a version-specific workaround. The breakpoint is 61 bytes from the
start of `LayerToLayer`, immediately after its call to `compSurfaceSublimation`
and before temporary vector allocation in this build. The runner requires
this SHA-256 of `libsnowpack.so.3.7.0`:

```
f1c11a0ac7e3c9b88810370f0e012f946a5b70073879a400f6f751cde897908f
```

The workaround requires GDB and permission to debug its own child process.
A different model build requires review of the guard rather than reusing the
instruction offset. The run log records the number of guard applications and
the status JSON records its command. Both raw TKG4 and DG1 depth and SWE matched every
original pre-crash output value in their temporary month-long verification runs;
both guarded runs completed that month. This check does not establish agreement
with a future upstream fix, so retain the workaround flag when interpreting
or publishing these model results.
