# api/gemini_client.py
import os
import re

# import google.generativeai as genai
from google import genai
from typing import List, Dict, Tuple, Any, Optional, Literal
from fastapi import HTTPException
from dotenv import load_dotenv

# --- Import Pydantic Models from api.models ---

# Corrected import path assuming api is a package or accessible
from models import (
    TextContent,
    MarkdownContent,
    FormContent,
    SxSContent,
    TextField,
    DropdownField,
    FormFieldWrapper,
    SxSRow,
)


load_dotenv()

# --- Configuration ---
API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    print("Warning: GEMINI_API_KEY environment variable not set.")

client = genai.Client(api_key=API_KEY)
# --- Constants for Parsing ---
FORM_PREFIX = "FORM::"
SXS_PREFIX = "SXS::"
# Basic regex to detect common markdown elements
MARKDOWN_REGEX = re.compile(
    r"(^#{1,6}\s|\n#{1,6}\s|^\*\s|\n\*\s|^- \s|\n- \s|^\d+\.\s|\n\d+\.\s|\*\*|__|\*|_|`|\[.*\]\(.*\))"
)

# --- Helper Functions ---

# --- Parsing Logic for Prefix-Based Output ---


def _parse_form_string(form_string: str) -> Optional[Dict[str, Any]]:
    """
    Parses a specially formatted string from Gemini into a FormContent dictionary structure.
    Format: FORM::Title;SubmitText;Label1|ID1|text[|Placeholder[|Initial]];Label2|ID2|dropdown|OptA,OptB[|Default]...
    Returns None if parsing fails.
    """
    try:
        parts = form_string.split(";", 2)  # Split Title; SubmitText; Fields...
        if len(parts) < 3:
            print(
                f"Form parsing failed: Not enough parts after splitting by ';'. Parts found: {len(parts)}"
            )
            return None
        title, submit_text, fields_part = parts
        title = title.strip()
        submit_text = submit_text.strip() or "Submit"  # Default submit text

        fields = []
        field_definitions = fields_part.split(";")
        print(f"Parsing form fields: {field_definitions}")
        for i, field_def in enumerate(field_definitions):
            if not field_def.strip():
                continue
            field_parts = field_def.split("|", 3)  # Split Label|ID|Type|Rest...
            if len(field_parts) < 3:
                print(
                    f"Skipping form field definition {i+1}: Not enough parts after splitting by '|'. Parts found: {len(field_parts)} in '{field_def}'"
                )
                continue  # Need at least Label, ID, Type
            label, field_id, field_type = [p.strip() for p in field_parts[:3]]
            rest = (
                field_parts[3].strip() if len(field_parts) > 3 else ""
            )  # Strip rest as well
            print(
                f"  Field {i+1}: Label='{label}', ID='{field_id}', Type='{field_type}', Rest='{rest}'"
            )

            field_wrapper_data = {}
            try:  # Add try-except around individual field processing
                if field_type == "text":
                    text_parts = rest.split("|", 1)  # Split Placeholder|Initial
                    placeholder = text_parts[0].strip() if text_parts else None
                    initial_value = (
                        text_parts[1].strip() if len(text_parts) > 1 else None
                    )
                    text_field_data = {
                        "label": label,
                        "field_id": field_id,
                        "type": "text",
                        "placeholder": placeholder or None,  # Ensure null if empty
                        "initial_value": initial_value or None,
                    }
                    TextField(**text_field_data)  # Validate
                    field_wrapper_data["text_field"] = text_field_data
                    print(f"    Parsed as text field: {text_field_data}")

                elif field_type == "dropdown":
                    dropdown_parts = rest.split("|", 1)  # Split Options|Default
                    options_str = dropdown_parts[0].strip()
                    options = [
                        opt.strip() for opt in options_str.split(",") if opt.strip()
                    ]
                    if not options:
                        print(
                            f"    Skipping dropdown field '{field_id}': No valid options found in '{options_str}'"
                        )
                        continue  # Skip if no options
                    default_option = (
                        dropdown_parts[1].strip() if len(dropdown_parts) > 1 else None
                    )
                    if default_option and default_option not in options:
                        print(
                            f"    Warning for dropdown field '{field_id}': Default option '{default_option}' not in options {options}. Resetting default."
                        )
                        default_option = None  # Validate default

                    dropdown_field_data = {
                        "label": label,
                        "field_id": field_id,
                        "type": "dropdown",
                        "options": options,
                        "default_option": default_option,
                    }

                    DropdownField(**dropdown_field_data)  # Validate
                    field_wrapper_data["dropdown_field"] = dropdown_field_data
                    print(f"    Parsed as dropdown field: {dropdown_field_data}")
                else:
                    print(
                        f"    Skipping field '{field_id}': Unknown type '{field_type}'"
                    )
                    continue  # Skip unknown type

                # Validate wrapper if Pydantic is available

                FormFieldWrapper(**field_wrapper_data)
                fields.append(field_wrapper_data)

            except Exception as field_parse_error:
                print(
                    f"    Error parsing field definition '{field_def}': {field_parse_error}"
                )
                continue  # Skip this field if it has errors

        if not fields:
            print("Form parsing failed: No valid fields were parsed.")
            return None  # No valid fields parsed

        form_content_data = {
            "title": title,
            "fields": fields,
            "submit_button_text": submit_text,
        }
        # Validate final structure if Pydantic is available
        FormContent(**form_content_data)
        print(f"Successfully parsed form content: {form_content_data}")
        return form_content_data

    except Exception as e:
        print(f"Error parsing form string: {e}\nString was: '{form_string}'")
        import traceback

        traceback.print_exc()
        return None


def _parse_sxs_string(sxs_string: str) -> Optional[Dict[str, Any]]:
    """
    Parses a specially formatted string from Gemini into an SxSContent dictionary structure.
    Format: SXS::Title;ModelALabel;ModelBLabel;Key1|Label1|ValA1|ValB1;Key2|Label2|ValA2|ValB2...
    Returns None if parsing fails.
    """
    try:
        parts = sxs_string.split(";", 3)  # Split Title; ModelA; ModelB; Rows...
        if len(parts) < 4:
            print(
                f"SxS parsing failed: Not enough parts after splitting by ';'. Parts found: {len(parts)}"
            )
            return None
        title, model_a_label, model_b_label, rows_part = parts
        title = title.strip()
        model_a_label = model_a_label.strip() or "Model A"
        model_b_label = model_b_label.strip() or "Model B"

        rows = []
        row_definitions = rows_part.split(";")
        print(f"Parsing SxS rows: {row_definitions}")
        for i, row_def in enumerate(row_definitions):
            if not row_def.strip():
                continue
            row_parts = row_def.split("|", 3)  # Split Key|Label|ValA|ValB
            if len(row_parts) != 4:
                print(
                    f"Skipping SxS row definition {i+1}: Expected 4 parts separated by '|', found {len(row_parts)} in '{row_def}'"
                )
                continue  # Must have all 4 parts
            key, label, value_a, value_b = [p.strip() for p in row_parts]

            row_data = {
                "key": key,
                "label": label,
                "value_model_a": value_a,
                "value_model_b": value_b,
            }
            # Validate with Pydantic if available
            try:  # Add try-except around validation
                SxSRow(**row_data)
                rows.append(row_data)
                print(f"  Row {i+1}: Parsed {row_data}")
            except Exception as row_validation_error:
                print(
                    f"  Error validating SxS row data {row_data}: {row_validation_error}"
                )
                continue  # Skip invalid rows

        if not rows:
            print("SxS parsing failed: No valid rows were parsed.")
            return None  # No valid rows parsed

        sxs_content_data = {
            "title": title,
            "model_a_label": model_a_label,
            "model_b_label": model_b_label,
            "rows": rows,
        }
        # Validate final structure if Pydantic is available
        SxSContent(**sxs_content_data)
        print(f"Successfully parsed SxS content: {sxs_content_data}")
        return sxs_content_data

    except Exception as e:
        print(f"Error parsing SxS string: {e}\nString was: '{sxs_string}'")
        import traceback

        traceback.print_exc()
        return None


def _format_history_for_gemini(
    chat_history: List[Dict[str, any]],
) -> List[Dict[str, any]]:
    """
    Formats the internal chat history (list of ChatMessage dicts)
    into the structure expected by the Gemini API (alternating user/model roles).
    Handles different content types by converting them to a text representation.
    """
    gemini_history = []
    for message in chat_history:
        role = message.get("role")
        gemini_role = "model" if role == "assistant" else role
        content_parts = []

        # --- Handle different message types ---
        response_type = message.get("response_type")

        if response_type == "text" and message.get("text_content"):
            content_parts.append({"text": message["text_content"].get("text", "")})
        elif response_type == "markdown" and message.get("markdown_content"):
            content_parts.append(
                {"text": message["markdown_content"].get("markdown", "")}
            )
        elif response_type == "form" and message.get("form_content"):
            form_data = message["form_content"]
            title = form_data.get("title", "Form")
            fields_repr = []
            for field_wrapper in form_data.get("fields", []):
                field = field_wrapper.get("text_field") or field_wrapper.get(
                    "dropdown_field"
                )
                if field:
                    label = field.get("label", field.get("field_id", "?"))
                    ftype = field.get("type", "?")
                    fields_repr.append(f"{label} ({ftype})")
            content_parts.append(
                {
                    "text": f"[Assistant presented a form: {title} with fields: {', '.join(fields_repr)}]"
                }
            )
        elif response_type == "sxs" and message.get("sxs_content"):
            sxs_data = message["sxs_content"]
            title = sxs_data.get("title", "Comparison")
            rows_count = len(sxs_data.get("rows", []))
            content_parts.append(
                {
                    "text": f"[Assistant presented a comparison table: {title} ({rows_count} rows)]"
                }
            )
        else:
            if message.get("text_content"):  # Default to text if type unknown/missing
                content_parts.append({"text": message["text_content"].get("text", "")})
            else:
                print(
                    f"Warning: Skipping message with unrecognized/missing content for Gemini history: {message}"
                )
                continue

        # Filter out empty parts before adding
        valid_parts = []
        for p in content_parts:
            if "text" in p and p["text"].strip():
                valid_parts.append(p)

        if valid_parts:
            gemini_history.append({"role": gemini_role, "parts": valid_parts})
        else:
            print(
                f"Warning: Skipping entry for role '{gemini_role}' due to empty parts after processing."
            )

    # --- Clean up history (Ensure alternating roles) ---
    cleaned_history = []
    if gemini_history:
        current_merged_entry = None
        for item in gemini_history:
            role = item["role"]
            parts = item.get("parts", [])
            if not isinstance(parts, list):
                parts = [parts]

            if current_merged_entry and current_merged_entry["role"] == role:
                current_merged_entry["parts"].extend(parts)
            else:
                if current_merged_entry:
                    cleaned_history.append(current_merged_entry)
                current_merged_entry = {"role": role, "parts": list(parts)}

        if current_merged_entry:
            cleaned_history.append(current_merged_entry)

    if cleaned_history and cleaned_history[-1]["role"] == "model":
        print("Warning: Formatted history ends with a 'model' role.")

    return cleaned_history


# --- Main Function ---


async def generate_gemini_chat_response(
    chat_history: List[Dict[str, any]],  # Expects list of dicts from session storage
    user_content: str,
    requested_response_type: Literal[
        "text", "markdown", "form", "sxs"
    ],  # Parameter remains
) -> Tuple[str, Dict[str, any]]:
    """
    Generates a chat response using the Gemini API (gemini-2.0-flash-lite)
    via controlled generation (prompting + prefix parsing) for the requested response type.

    Args:
        chat_history: List of previous ChatMessage objects (as dicts) in the session.
        user_content: The latest message text from the user.
        requested_response_type: The desired format ('text', 'markdown', 'form', 'sxs').

    Returns:
        A tuple containing:
        - actual_response_type: The type of content actually generated ('text', 'markdown', 'form', 'sxs').
                                This might differ from requested_type if generation failed or parsing failed.
        - content_dict: A dictionary structured for the corresponding ChatMessage
                        content field (e.g., {'text_content': {...}}, {'form_content': {...}}).

    Raises:
        HTTPException: If the model is not initialized. API call errors are handled internally.
    """

    # Format the history
    formatted_history = _format_history_for_gemini(chat_history)

    # --- Construct the dynamic instruction prompt for Controlled Generation ---
    response_schema = None
    if requested_response_type == "form":
        response_schema = FormContent
    elif requested_response_type == "sxs":
        response_schema = SxSContent
    elif requested_response_type == "markdown":
        response_schema = MarkdownContent
    else:  # 'text'
        response_schema = MarkdownContent

    # Combine history, instructions, and the new user message
    current_turn_content = [
        *formatted_history,
        {"role": "user", "parts": [{"text": user_content}]},
    ]

    try:
        print(
            f"Sending to Gemini. Requesting type: '{requested_response_type}'. Using Controlled Generation (Prefixes). User content: '{user_content[:50]}...'"
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=current_turn_content,
            config={
                "response_mime_type": "application/json",
                "response_schema": response_schema,
            },
        )
        # response = await model.generate_content_async(
        #     contents=current_turn_content,
        #     generation_config=genai.types.GenerationConfig(
        #         response_mime_type="application/json", response_schema=response_schema
        #     ),  # Optional
        # )

        # --- Response Handling ---
        response_part = None
        response_text = ""  # Fallback text content
        actual_response_type = "text"  # Default actual type
        content_dict = {}

        # Check for safety issues or empty response first
        if not response.candidates:
            reason = "Unknown"
            try:
                reason = response.prompt_feedback.block_reason.name
            except Exception:
                pass
            print(f"Warning: Gemini response was blocked or empty. Reason: {reason}")
            response_text = f"(Response blocked by safety filters: {reason})"
            content_dict = {"text_content": {"text": response_text}}  # Fallback to text
        elif not response.candidates[0].content.parts:
            finish_reason = "Unknown"
            try:
                finish_reason = response.candidates[0].finish_reason.name
            except Exception:
                pass
            print(
                f"Warning: Gemini response candidate contained no parts. Finish Reason: {finish_reason}"
            )
            response_text = (
                f"(No response text received. Finish Reason: {finish_reason})"
            )
            content_dict = {"text_content": {"text": response_text}}  # Fallback to text
        else:
            # Get the first part of the response
            response_part = response.candidates[0].content.parts[0]
            # Extract text
            if hasattr(response_part, "text"):
                # IMPORTANT: Do NOT strip whitespace here initially, as prefixes might be紧跟
                # response_text = response_part.text
                # Let's strip later after checking prefixes
                response_text = response_part.text
            else:
                response_text = (
                    "(Received non-text response part)"  # Handle unexpected part types
                )

            print(
                f"Received Gemini response (raw): '{response_text[:200]}...'"
            )  # Log more for debugging prefixes

            # --- Check for Prefixes ---
            # Check prefixes *before* stripping general whitespace
            if requested_response_type == "form" and response_text.startswith(
                FORM_PREFIX
            ):
                print("Detected FORM prefix.")
                # Pass the string *without* the prefix to the parser
                form_data = _parse_form_string(
                    response_text[len(FORM_PREFIX) :].strip()
                )  # Strip *after* removing prefix
                if form_data:
                    actual_response_type = "form"
                    content_dict = {"form_content": form_data}
                    print("Successfully parsed FORM data.")
                else:
                    print(
                        "Failed to parse FORM string after prefix detection, falling back to text."
                    )
                    actual_response_type = "text"
                    content_dict = {
                        "text_content": {
                            "text": f"(Failed to parse form)\n{response_text.strip()}"
                        }
                    }  # Return stripped original text

            elif requested_response_type == "sxs" and response_text.startswith(
                SXS_PREFIX
            ):
                print("Detected SXS prefix.")
                # Pass the string *without* the prefix to the parser
                sxs_data = _parse_sxs_string(
                    response_text[len(SXS_PREFIX) :].strip()
                )  # Strip *after* removing prefix
                if sxs_data:
                    actual_response_type = "sxs"
                    content_dict = {"sxs_content": sxs_data}
                    print("Successfully parsed SXS data.")
                else:
                    print(
                        "Failed to parse SXS string after prefix detection, falling back to text."
                    )
                    actual_response_type = "text"
                    content_dict = {
                        "text_content": {
                            "text": f"(Failed to parse SxS table)\n{response_text.strip()}"
                        }
                    }

            # --- Process as Text/Markdown if no prefix matched (or if requested) ---
            else:
                # Now strip whitespace for text/markdown processing
                response_text = response_text.strip()

                if requested_response_type == "markdown":
                    print("Processing response as Markdown (as requested).")
                    actual_response_type = "markdown"
                    content_dict = {"markdown_content": {"markdown": response_text}}
                    # Optional: Validate Markdown structure if needed

                    try:
                        MarkdownContent(**content_dict["markdown_content"])
                    except Exception as md_error:
                        print(
                            f"Warning: Pydantic validation failed for MarkdownContent: {md_error}"
                        )

                else:  # Default to 'text' (or if 'text' was explicitly requested, or if prefix parsing failed/missing)
                    print(
                        f"Processing response as Text (requested: '{requested_response_type}', actual: '{actual_response_type}')."
                    )
                    actual_response_type = "text"  # Ensure actual type is text here
                    content_dict = {"text_content": {"text": response_text}}
                    # Optional: Validate Text structure
                    try:
                        TextContent(**content_dict["text_content"])
                    except Exception as txt_error:
                        print(
                            f"Warning: Pydantic validation failed for TextContent: {txt_error}"
                        )

        # Ensure content_dict is not empty before returning
        if not content_dict:
            print(
                "Error: content_dict is empty after processing. Falling back to error text."
            )
            actual_response_type = "text"
            content_dict = {
                "text_content": {
                    "text": "(Internal error: Failed to generate response content)"
                }
            }

        return actual_response_type, content_dict

    except Exception as e:
        print(f"Error during Gemini API call or response processing: {e}")
        import traceback

        print(traceback.format_exc())  # Print full traceback for debugging
        # Fallback to returning an error message as text
        error_text = f"An error occurred while communicating with the LLM: {e}"
        # Return 'text' type with the error message
        return "text", {"text_content": {"text": error_text}}
