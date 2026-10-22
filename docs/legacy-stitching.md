# Legacy sampled-pose stitching

Use [typed-step stitching](stitching.md) for ordinary joins. The following method is retained for existing callers.

### Advanced sampled-pose stitching

`motions.create_stitched_motion(character_id, prefix, suffix)` uses the enhanced
stitch preview API; its `_sync` variant has the same arguments. It returns a new
`Motion` dictionary synchronously. This is separate from single-motion looping.

Each clip is a `StitchParams` (import with `from uthana import StitchParams`)
containing its motion ID, duration,
trim times in seconds and matching fractions, root world position/rotation, and
pelvis states at zero/lower/upper trim. See the
[complete API input contract](https://uthana.com/docs/api/capabilities/stitching-sampled-poses).
Use `stitch_loop=False`, a positive `stitch_duration` (recommended 0.1–3 seconds),
and `prompt=""` unless a transition prompt is intended. The prefix determines
transition settings; keep both inputs consistent.

```python
import httpx

# prefix_samples and suffix_samples are full StitchParams from your motion loader.
stitched = await uthana_client.motions.create_stitched_motion(
    character_id, prefix_samples, suffix_samples,
    timeout=httpx.Timeout(360, connect=15),
)
print(stitched["id"])
```

Supply real poses sampled on the same target character in a shared world scene.
Positions are meters in Y-up space (x/z horizontal), rotations are approximately
unit x/y/z/w quaternions, and facing yaw is in radians. The client validates
fields, finite values, quaternion length, and trim time/fraction consistency
before submitting. It copies validated inputs and never supplies guessed poses,
samples animations, aligns the scene, or automatically retries a mutation.

Stitching defaults to 360-second HTTP phase limits and 15 seconds to connect when
`timeout` is omitted or `None`; an explicit value overrides them. Allow the host
enough time for the synchronous stitch or loop (at least 420 seconds with these
phase limits, longer for transfers). Phase timeouts are not an overall deadline.
If either response lacks a nonempty motion ID, the client raises
`UthanaError(kind="uncertain")`: inspect existing work before resubmitting.
Stitching keeps its published price per generated output second.
Real playback and contact review are
still required to establish transition quality. No pose-loader dependency is
added to the Python client.

