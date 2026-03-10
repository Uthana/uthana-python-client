# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""GraphQL query and mutation strings for the Uthana API."""


class _GraphQL:
    """Namespace for GraphQL query and mutation strings. Use: from uthana.graphql import q."""

    TEXT_TO_MOTION_VQVAE_V1 = """
mutation TextToMotion(
    $prompt: String!,
    $character_id: String,
    $model: String!,
    $foot_ik: Boolean
) {
    create_text_to_motion(
        prompt: $prompt,
        character_id: $character_id,
        model: $model,
        foot_ik: $foot_ik
    ) {
        motion {
            id
            name
        }
    }
}
"""

    TEXT_TO_MOTION_DIFFUSION_V2 = """
mutation CreateTextToMotion(
    $prompt: String!,
    $character_id: String,
    $model: String!,
    $foot_ik: Boolean,
    $cfg_scale: Float,
    $length: Float,
    $seed: Int,
    $retargeting_ik: Boolean
) {
    create_text_to_motion(
        prompt: $prompt,
        character_id: $character_id,
        model: $model,
        foot_ik: $foot_ik,
        cfg_scale: $cfg_scale,
        length: $length,
        seed: $seed,
        retargeting_ik: $retargeting_ik
    ) {
        motion {
            id
            name
        }
    }
}
"""

    CREATE_CHARACTER = """
mutation CreateCharacter(
    $name: String!,
    $file: Upload!,
    $auto_rig: Boolean,
    $auto_rig_front_facing: Boolean
) {
    create_character(
        name: $name,
        file: $file,
        auto_rig: $auto_rig,
        auto_rig_front_facing: $auto_rig_front_facing
    ) {
        character {
            id
            name
        }
        auto_rig_confidence
    }
}
"""

    CREATE_VIDEO_TO_MOTION = """
mutation CreateVideoToMotion($file: Upload!, $motion_name: String!, $model: String) {
    create_video_to_motion(file: $file, motion_name: $motion_name, model: $model) {
        job {
            id
            status
        }
    }
}
"""

    GET_JOB = """
query GetJob($job_id: String!) {
    job(job_id: $job_id) {
        id
        status
        result
    }
}
"""

    LIST_JOBS = """
query ListJobs($method: String) {
    jobs(method: $method) {
        id
        status
        method
        created
        updated
    }
}
"""

    LIST_MOTIONS = """
query {
    motions {
        id
        name
        created
    }
}
"""

    LIST_CHARACTERS = """
query {
    characters {
        id
        name
        created
        updated
    }
}
"""

    GET_USER = """
query {
    user {
        id
        name
        email
        email_verified
    }
}
"""

    GET_ORG = """
query {
    org {
        id
        name
        motion_download_secs_per_month
        motion_download_secs_per_month_remaining
    }
}
"""

    CREATE_IMAGE_FROM_TEXT = """
mutation CreateImageFromText($prompt: String!) {
    create_image_from_text(prompt: $prompt) {
        character_id
        images {
            key
            url
        }
    }
}
"""

    CREATE_IMAGE_FROM_IMAGE = """
mutation CreateImageFromImage($file: Upload!) {
    create_image_from_image(file: $file) {
        character_id
        image {
            key
            url
        }
    }
}
"""

    CREATE_CHARACTER_FROM_IMAGE = """
mutation CreateCharacterFromImage(
    $character_id: String!,
    $image_key: String!,
    $prompt: String!,
    $name: String
) {
    create_character_from_image(
        character_id: $character_id,
        image_key: $image_key,
        prompt: $prompt,
        name: $name
    ) {
        character {
            id
            name
        }
        auto_rig_confidence
    }
}
"""

    CREATE_MOTION_FROM_GLTF = """
mutation create_motion_from_gltf($gltf: String!, $motionName: String!, $characterId: String) {
    create_motion_from_gltf(gltf: $gltf, motion_name: $motionName, character_id: $characterId) {
        motion { id }
    }
}
"""

    UPDATE_MOTION = """
mutation update_motion($id: String!, $name: String, $deleted: Boolean) {
    update_motion(id: $id, name: $name, deleted: $deleted) {
        id
        name
        deleted
    }
}
"""

    CREATE_MOTION_FAVORITE = """
mutation create_motion_favorite($motion_id: String!) {
    create_motion_favorite(motion_id: $motion_id) {
        id
        motion_id
    }
}
"""

    DELETE_MOTION_FAVORITE = """
mutation delete_motion_favorite($motion_id: String!) {
    delete_motion_favorite(motion_id: $motion_id) {
        id
    }
}
"""


q = _GraphQL()
