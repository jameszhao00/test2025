# api/models.py
from typing import List, Literal, Optional, Union, Dict, Any
from pydantic import BaseModel, Field, validator, root_validator

# --- Content Type Models ---

class TextContent(BaseModel):
    text: str

class MarkdownContent(BaseModel):
    markdown: str

# --- Form Field Definitions ---
class BaseField(BaseModel):
    label: str
    field_id: str

class TextField(BaseField):
    type: Literal['text'] = 'text'
    placeholder: Optional[str] = None
    initial_value: Optional[str] = None

class DropdownField(BaseField):
    type: Literal['dropdown'] = 'dropdown'
    options: List[str]
    default_option: Optional[str] = None

    @validator('default_option')
    def check_default(cls, v, values):
        if v is not None and 'options' in values and v not in values['options']:
            raise ValueError('default_option must be one of the available options')
        return v

# --- Form Field Wrapper ---
class FormFieldWrapper(BaseModel):
    text_field: Optional[TextField] = Field(default=None, description="Contains data if the field is a text input.")
    dropdown_field: Optional[DropdownField] = Field(default=None, description="Contains data if the field is a dropdown.")

    @root_validator(pre=False, skip_on_failure=True)
    def check_exactly_one_field(cls, values):
        """Ensures that exactly one field type (text_field or dropdown_field) is populated."""
        populated = [k for k, v in values.items() if v is not None]
        if len(populated) != 1:
            raise ValueError(f"Exactly one field type (text_field or dropdown_field) must be provided per FormFieldWrapper. Found: {populated}")
        return values

    # --- Optional Helper Properties (Not directly part of the schema, but useful internally) ---
    @property
    def field(self) -> Union[TextField, DropdownField]:
        """Returns the actual populated field object (TextField or DropdownField)."""
        if self.text_field:
            return self.text_field
        elif self.dropdown_field:
            return self.dropdown_field
        else:
            raise ValueError("FormFieldWrapper is unexpectedly empty") # Should be prevented by validator

    @property
    def field_id(self) -> str:
        """Returns the field_id of the populated field."""
        return self.field.field_id

    @property
    def type(self) -> Literal['text', 'dropdown']:
        """Returns the type ('text' or 'dropdown') of the populated field."""
        return self.field.type

    @property
    def label(self) -> str:
         """Returns the label of the populated field."""
         return self.field.label

# --- Form Content Definition ---
class FormContent(BaseModel):
    title: str
    fields: List[FormFieldWrapper] = Field(description="A list of fields in the form, each wrapped to specify its type.")
    submit_button_text: str = "Submit"

# --- SxS Definitions ---
class SxSRow(BaseModel):
    key: str
    label: str
    value_model_a: str
    value_model_b: str

class SxSContent(BaseModel):
    title: str
    model_a_label: str = "Model A"
    model_b_label: str = "Model B"
    rows: List[SxSRow]

# --- Chat Message Model ---
class ChatMessage(BaseModel):
    """ Represents a single message in the chat (without a server-side ID). """
    session_id: str
    role: Literal['user', 'assistant']
    response_type: Literal['text', 'markdown', 'form', 'sxs'] # Discriminator for content

    # Optional fields for content types
    text_content: Optional[TextContent] = None
    markdown_content: Optional[MarkdownContent] = None
    form_content: Optional[FormContent] = None
    sxs_content: Optional[SxSContent] = None

    @root_validator(pre=False, skip_on_failure=True)
    def check_content_consistency(cls, values):
        response_type = values.get('response_type')
        content_fields = {
            'text': values.get('text_content'),
            'markdown': values.get('markdown_content'),
            'form': values.get('form_content'),
            'sxs': values.get('sxs_content'),
        }
        populated_fields = [k for k, v in content_fields.items() if v is not None]

        if len(populated_fields) == 0:
             pass # Allow empty during construction
        elif len(populated_fields) > 1:
            raise ValueError(f"Multiple content fields populated: {', '.join(populated_fields)}")
        elif populated_fields[0] != response_type:
            raise ValueError(f"Content field '{populated_fields[0]}' does not match response_type '{response_type}'")
        return values

# --- API Request/Response Models ---
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    content: str

class ChatResponse(BaseModel):
    session_id: str
    reply: ChatMessage # Contains the assistant's reply message

class FetchMessagesResponse(BaseModel):
    messages: List[ChatMessage] # Contains the list of messages in the history
