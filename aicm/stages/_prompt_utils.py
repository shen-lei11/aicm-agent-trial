"""Prompt utilities for pipeline stages."""


def split_template(template: str) -> tuple[str, str]:
    """Split template into (system_prompt, user_prompt).

    Templates use ### SYSTEM ROLE at the top and ### USER COMMAND or
    ### INPUT CONTEXTS as the boundary where the user message begins.
    """
    user_section_markers = ["### USER COMMAND", "### INPUT CONTEXTS"]
    for marker in user_section_markers:
        if marker in template:
            idx = template.index(marker)
            system = template[:idx].strip()
            user = template[idx:].strip()
            # Strip the leading ### SYSTEM ROLE header from system section
            if system.startswith("### SYSTEM ROLE"):
                system = system[len("### SYSTEM ROLE"):].strip()
            return system, user

    # Fallback: entire template is the user prompt
    return "", template.strip()
