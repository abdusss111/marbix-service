# Prompt Management System

A comprehensive system for managing AI prompts in the database, eliminating the need to hardcode prompts throughout your application.

## 🏗️ Architecture Overview

The system follows a layered architecture pattern:

```
API Layer (FastAPI) → Service Layer → CRUD Layer → Database
```

### Components

1. **Models** (`src/marbix/models/prompt.py`)
   - Database schema for prompts
   - Includes fields for versioning, usage tracking, and metadata

2. **Schemas** (`src/marbix/schemas/prompt.py`)
   - Pydantic models for API requests/responses
   - Input validation and serialization

3. **CRUD Operations** (`src/marbix/crud/prompt.py`)
   - Database operations (Create, Read, Update, Delete)
   - Search and filtering capabilities

4. **Service Layer** (`src/marbix/services/prompt_service.py`)
   - Business logic and validation
   - Error handling and business rules

5. **API Endpoints** (`src/marbix/api/v1/prompts.py`)
   - RESTful API for prompt management
   - Authentication and authorization

6. **Utility Functions** (`src/marbix/utils/prompt_utils.py`)
   - Easy prompt retrieval functions
   - Template variable substitution

## 🚀 Quick Start

### 1. Run Database Migration

```bash
# Navigate to your project directory
cd src/marbix

# Run the migration to create the prompts table
alembic upgrade head
```

### 2. Seed Initial Prompts

```bash
# Run the seeding script
python scripts/seed_prompts.py
```

### 3. Use Prompts in Your Code

```python
from marbix.utils.prompt_utils import get_prompt_content_by_name, get_formatted_prompt

# Get a prompt by name
prompt_content = get_prompt_content_by_name(db, "business_strategy_generator")

# Get a prompt with variable substitution
formatted_prompt = get_formatted_prompt(
    db, 
    "business_strategy_generator",
    business_type="Restaurant",
    business_goal="Increase revenue by 30%",
    location="Downtown",
    promotion_budget="$5000",
    team_budget="$10000"
)
```

## 📚 API Endpoints

### Create Prompt
```http
POST /api/v1/prompts
Content-Type: application/json

{
  "name": "my_prompt",
  "description": "A description of the prompt",
  "content": "You are an AI assistant...",
  "category": "general",
  "tags": ["ai", "assistant"],
  "is_active": true
}
```

### Get Prompts
```http
GET /api/v1/prompts?skip=0&limit=10&category=business&search=strategy
```

### Get Prompt by ID
```http
GET /api/v1/prompts/{prompt_id}?increment_usage=true
```

### Update Prompt
```http
PUT /api/v1/prompts/{prompt_id}
Content-Type: application/json

{
  "content": "Updated prompt content...",
  "is_active": false
}
```

### Delete Prompt
```http
DELETE /api/v1/prompts/{prompt_id}
```

### Search Prompts
```http
GET /api/v1/prompts/search?q=marketing&skip=0&limit=20
```

## 🔧 Usage Examples

### Basic Prompt Retrieval

```python
from marbix.utils.prompt_utils import get_prompt_content_by_name

# Simple retrieval
prompt = get_prompt_content_by_name(db, "email_template_generator")
if prompt:
    print(f"Using prompt: {prompt}")
```

### Prompt with Variables

```python
from marbix.utils.prompt_utils import get_formatted_prompt

# Prompt with dynamic variables
email_prompt = get_formatted_prompt(
    db,
    "email_template_generator",
    email_purpose="Customer Onboarding",
    recipient_type="New Customer",
    tone="Professional and Welcoming",
    key_message="Welcome to our service!",
    call_to_action="Schedule your first consultation"
)

# Use the formatted prompt
response = ai_model.generate(email_prompt)
```

### In Your Existing Services

```python
# Before (hardcoded)
def generate_business_strategy(business_data):
    prompt = """You are a business strategy expert. Based on the following information..."""
    # ... rest of the function

# After (database-driven)
def generate_business_strategy(business_data):
    from marbix.utils.prompt_utils import get_formatted_prompt
    
    prompt = get_formatted_prompt(
        db,
        "business_strategy_generator",
        **business_data
    )
    
    if not prompt:
        raise ValueError("Business strategy prompt not found")
    
    # ... rest of the function
```

## 🏷️ Prompt Categories

The system includes several predefined categories:

- **business_strategy**: Business planning and strategy prompts
- **content_optimization**: Content improvement and SEO prompts
- **customer_service**: Customer support and communication prompts
- **data_analysis**: Data reporting and analysis prompts
- **communication**: Email and general communication prompts

## 🔍 Search and Filtering

### By Category
```python
from marbix.services.prompt_service import PromptService

# Get all business strategy prompts
business_prompts = await PromptService.get_prompts_by_category(db, "business_strategy")
```

### By Search Query
```python
# Search across name, description, and content
search_results = await PromptService.get_prompts(
    db, 
    search="marketing",
    limit=20
)
```

### Active Prompts Only
```python
# Get only active prompts
active_prompts = await PromptService.get_active_prompts(db)
```

## 📊 Usage Tracking

The system automatically tracks:

- **Usage Count**: How many times each prompt has been used
- **Last Used**: Timestamp of the last usage
- **Created/Updated**: Audit trail for changes

```python
# Increment usage when using a prompt
from marbix.services.prompt_service import PromptService

await PromptService.increment_usage(db, prompt_id)
```

## 🔮 Future Enhancements

### Versioning System
- **Prompt History**: Track all versions of a prompt
- **Rollback Capability**: Revert to previous versions
- **Version Comparison**: Compare different versions side-by-side

### Advanced Features
- **Prompt Templates**: Reusable prompt structures
- **Variable Validation**: Ensure required variables are provided
- **Prompt Performance**: Track success rates and user feedback
- **A/B Testing**: Test different prompt variations
- **Prompt Analytics**: Usage patterns and effectiveness metrics

### Integration Features
- **Webhook Support**: Notify external systems of prompt changes
- **API Rate Limiting**: Control prompt usage frequency
- **Prompt Caching**: Redis-based caching for frequently used prompts
- **Multi-language Support**: Localized prompts for different regions

## 🛡️ Security and Access Control

- **User Authentication**: All endpoints require valid user authentication
- **Role-based Access**: Different permissions for different user roles
- **Audit Logging**: Track who created/modified prompts
- **Input Validation**: Prevent malicious prompt content

## 🧪 Testing

### Run the Seeding Script
```bash
python scripts/seed_prompts.py
```

### Test API Endpoints
```bash
# Create a prompt
curl -X POST "http://localhost:8000/api/v1/prompts" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "test_prompt", "content": "Test content"}'

# Get prompts
curl "http://localhost:8000/api/v1/prompts" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 📝 Best Practices

1. **Naming Convention**: Use descriptive, consistent names for prompts
2. **Categorization**: Organize prompts by function and domain
3. **Variable Naming**: Use clear, descriptive variable names in templates
4. **Documentation**: Include detailed descriptions for each prompt
5. **Testing**: Test prompts with various inputs before production use
6. **Version Control**: Use the versioning system for important changes

## 🚨 Troubleshooting

### Common Issues

1. **Prompt Not Found**
   - Check if the prompt name is correct
   - Verify the prompt is active (`is_active = true`)
   - Ensure the database migration has been run

2. **Variable Substitution Errors**
   - Check that all required variables are provided
   - Verify variable names match the template placeholders
   - Use the `format_prompt_with_variables` function for debugging

3. **Database Connection Issues**
   - Verify database configuration
   - Check if the prompts table exists
   - Run `alembic current` to check migration status

### Debug Mode

Enable debug logging to see detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📞 Support

For issues or questions about the prompt management system:

1. Check this README for common solutions
2. Review the API documentation
3. Check the database migration status
4. Verify prompt data in the database

---

**Note**: This system is designed to be extensible. The versioning and parent_id fields are prepared for future enhancements but are not yet fully implemented in the current version.
