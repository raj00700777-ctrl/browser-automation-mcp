import json
import os
import re
import tempfile
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

WORKFLOW_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "workflows"
)

os.makedirs(
    WORKFLOW_DIR,
    exist_ok=True,
)


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _validate_name(name: str):
    if not isinstance(name, str):
        raise TypeError(
            "Workflow name must be a string."
        )

    name = name.strip()

    if not name:
        raise ValueError(
            "Workflow name cannot be empty."
        )

    return name


def _workflow_path(name: str):
    """
    Convert a workflow name into a safe JSON filename.
    """

    name = _validate_name(name)

    safe_name = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]',
        "_",
        name,
    )

    safe_name = re.sub(
        r"\s+",
        " ",
        safe_name,
    ).strip()

    safe_name = safe_name.rstrip(". ")

    if not safe_name:
        raise ValueError(
            "Invalid workflow name."
        )

    return os.path.join(
        WORKFLOW_DIR,
        safe_name + ".json",
    )


def _validate_steps(steps):
    """
    Validate workflow step structure without imposing
    a specific planner format.
    """

    if not isinstance(steps, list):
        raise TypeError(
            "Workflow steps must be a list."
        )

    return steps


def _write_json_atomic(path, data):
    """
    Write JSON through a temporary file and replace the
    destination only after the complete file is written.
    """

    directory = os.path.dirname(path)

    fd, temp_path = tempfile.mkstemp(
        prefix=".workflow_",
        suffix=".tmp",
        dir=directory,
    )

    try:

        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False,
            )

            file.flush()
            os.fsync(file.fileno())

        os.replace(
            temp_path,
            path,
        )

    except Exception:

        try:
            os.remove(temp_path)
        except OSError:
            pass

        raise


# ============================================================
# SAVE WORKFLOW
# ============================================================

def save_workflow(name: str, steps: list):
    """
    Save a workflow definition.

    Existing API preserved:
        save_workflow(name, steps)
    """

    try:

        name = _validate_name(name)
        steps = _validate_steps(steps)

        path = _workflow_path(name)

        now = datetime.now().isoformat()

        workflow = {
            "name": name,
            "created_at": now,
            "updated_at": now,
            "version": 1,
            "steps": steps,
        }

        _write_json_atomic(
            path,
            workflow,
        )

        return {
            "success": True,
            "message": "Workflow saved",
            "name": name,
            "path": path,
            "steps": len(steps),
            "version": 1,
        }

    except Exception as error:

        return {
            "success": False,
            "error": str(error),
            "name": name,
        }


# ============================================================
# LOAD WORKFLOW
# ============================================================

def load_workflow(name: str):
    """
    Load a saved workflow.
    """

    try:

        path = _workflow_path(name)

    except Exception as error:

        return {
            "success": False,
            "error": str(error),
            "name": name,
        }

    if not os.path.exists(path):

        return {
            "success": False,
            "error": "Workflow not found",
            "name": name,
            "path": path,
        }

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            workflow = json.load(file)

        if not isinstance(
            workflow,
            dict,
        ):
            return {
                "success": False,
                "error": (
                    "Workflow file contains "
                    "invalid data."
                ),
                "name": name,
            }

        steps = workflow.get(
            "steps",
            [],
        )

        if not isinstance(
            steps,
            list,
        ):
            return {
                "success": False,
                "error": (
                    "Workflow steps are not "
                    "stored as a list."
                ),
                "name": name,
            }

        return {
            "success": True,
            "workflow": workflow,
        }

    except json.JSONDecodeError as error:

        return {
            "success": False,
            "error": (
                "Workflow JSON is corrupted: "
                + str(error)
            ),
            "name": name,
            "path": path,
        }

    except Exception as error:

        return {
            "success": False,
            "error": str(error),
            "name": name,
            "path": path,
        }


# ============================================================
# LIST WORKFLOWS
# ============================================================

def list_workflows():
    """
    Return metadata for all valid and invalid workflow files.
    """

    try:

        files = [
            filename
            for filename in os.listdir(
                WORKFLOW_DIR
            )
            if filename.lower().endswith(
                ".json"
            )
        ]

    except Exception as error:

        return {
            "success": False,
            "count": 0,
            "workflows": [],
            "error": str(error),
        }

    workflows = []

    for filename in sorted(
        files,
        key=str.lower,
    ):

        path = os.path.join(
            WORKFLOW_DIR,
            filename,
        )

        try:

            with open(
                path,
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(file)

            if not isinstance(
                data,
                dict,
            ):
                raise ValueError(
                    "Workflow data is not an object."
                )

            steps = data.get(
                "steps",
                [],
            )

            if not isinstance(
                steps,
                list,
            ):
                raise ValueError(
                    "Workflow steps are invalid."
                )

            workflows.append({
                "name": data.get(
                    "name",
                    filename[:-5],
                ),
                "steps": len(steps),
                "created_at": data.get(
                    "created_at",
                ),
                "updated_at": data.get(
                    "updated_at",
                ),
                "version": data.get(
                    "version",
                    1,
                ),
                "file": path,
                "valid": True,
            })

        except Exception as error:

            workflows.append({
                "name": filename[:-5],
                "file": path,
                "valid": False,
                "error": str(error),
            })

    return {
        "success": True,
        "count": len(workflows),
        "workflows": workflows,
    }


# ============================================================
# DELETE WORKFLOW
# ============================================================

def delete_workflow(name: str):
    """
    Delete a saved workflow.

    Added as a separate explicit operation.
    """

    try:

        path = _workflow_path(name)

    except Exception as error:

        return {
            "success": False,
            "error": str(error),
        }

    if not os.path.exists(path):

        return {
            "success": False,
            "error": "Workflow not found",
            "name": name,
        }

    try:

        os.remove(path)

        return {
            "success": True,
            "message": "Workflow deleted",
            "name": name,
            "path": path,
        }

    except Exception as error:

        return {
            "success": False,
            "error": str(error),
            "name": name,
        }


# ============================================================
# WORKFLOW EXISTS
# ============================================================

def workflow_exists(name: str):
    """
    Check whether a workflow exists.
    """

    try:

        path = _workflow_path(name)

        return {
            "success": True,
            "exists": os.path.isfile(path),
            "name": name,
            "path": path,
        }

    except Exception as error:

        return {
            "success": False,
            "exists": False,
            "error": str(error),
            "name": name,
        }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "WORKFLOW_DIR",
    "save_workflow",
    "load_workflow",
    "list_workflows",
    "delete_workflow",
    "workflow_exists",
]