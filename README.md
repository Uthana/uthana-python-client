uthana-api
=================

Python wrapper around uthana's http api.

## Install

```bash
pip install uthana
```

## Usage

### Auto-Rig a Character

Upload a GLB or FBX mesh and get back a rigged character:

```python
from uthana import Client

client = Client("your-api-key")

# Upload and auto-rig a mesh file
output = client.create_character("path/to/character.glb")

print(output.character_id)        # character ID for use with other endpoints
print(output.auto_rig_confidence) # confidence score of the auto-rig

# Download the rigged character
data = client.download_character(output.character_id, output_format="glb")
with open("character_rigged.glb", "wb") as f:
    f.write(data)
```

### Text to Motion (v1)

Generate a motion clip from a text prompt:

```python
from uthana import Client

client = Client("your-api-key")

# Generate motion from a text prompt
output = client.create_text_to_motion("vqvae-v1", "a person walking forward")

print(output.character_id)
print(output.motion_id)

# Download as GLB at 30 fps
data = client.download_motion(
    output.character_id,
    output.motion_id,
    output_format="glb",
    fps=30,
)
with open("walking_forward.glb", "wb") as f:
    f.write(data)
```
