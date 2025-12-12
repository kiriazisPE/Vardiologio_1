# Shift Planner Pro — Complete Documentation

## 🌟 Overview

**Shift Planner Pro** is a modern, AI-powered employee scheduling application built with Streamlit. It provides comprehensive tools for managing work schedules, tracking employee availability, enforcing labor regulations, and generating analytics.

## ✨ Key Features

### 🤖 Intelligent Scheduling
- **Automatic Schedule Generation**: AI-powered algorithm respects employee availability, role requirements, and labor laws
- **MILP Optimization**: Optional PuLP-based optimizer for mathematically optimal schedules
- **Rule Compliance**: Automatic validation against configurable labor regulations
- **Auto-Fix**: Intelligent correction of scheduling violations

### 👥 Employee Management
- **Comprehensive Profiles**: Track roles, availability, and preferences
- **Multi-Role Support**: Employees can have multiple roles with different priorities
- **Availability Management**: Define which shifts each employee can work
- **Bulk Operations**: Import/export employee data

### 📊 Advanced Analytics
- **Interactive Visualizations**: Plotly-powered charts and graphs
- **Workload Analysis**: Fair distribution tracking and variance monitoring
- **Role Coverage Heatmaps**: Visual representation of staffing levels
- **Timeline Views**: Gantt-style shift timelines
- **KPI Dashboard**: Real-time metrics and indicators

### 📅 Visual Schedule Builder
- **Calendar View**: Monthly calendar with shift indicators
- **Weekly Timeline**: Hour-by-hour staffing overview
- **Drag-and-Drop Editor**: Interactive grid-based schedule editing
- **Role Assignment**: Quick role selection per shift

### 🔄 Shift Swaps
- **Employee Requests**: Staff can request shift exchanges
- **Manager Approval**: Workflow for reviewing and approving swaps
- **Automatic Application**: Approved swaps update schedule immediately
- **Audit Trail**: Track all swap requests and decisions

### 📥 Import/Export
- **Excel Export**: Multi-sheet workbooks with schedule, employees, stats, and violations
- **CSV Support**: Simple text format for universal compatibility
- **Import Validation**: Automatic checking of imported data
- **Template Generation**: Create starter files for data import

### 🎨 Modern UI/UX
- **Light/Dark Theme**: Fully customizable appearance
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Fragments**: Fast, granular updates without full page reloads
- **Dialogs**: Modal windows for focused interactions
- **Toast Notifications**: Non-intrusive feedback messages
- **Progress Tracking**: Visual indicators for multi-step operations

### 📖 User Assistance
- **Interactive Onboarding**: Step-by-step tour for new users
- **Contextual Help**: Page-specific guidance and tips
- **Keyboard Shortcuts**: Power user features
- **User Guide**: Comprehensive in-app documentation

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- pip or conda package manager

### Installation

1. **Clone or download the project**
```bash
cd shift_planner
```

2. **Create virtual environment** (recommended)
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**

Create `.env` file:
```env
APP_ENV=dev
DB_FILE=shifts.db
SERVER_PORT=8501
SESSION_TTL_MIN=240
TZ=Europe/Athens
LOG_LEVEL=INFO
AUTH_ENABLED=false
DEV_AUTH_FALLBACK=true
```

5. **Run the application**
```bash
streamlit run main.py
```

Visit `http://localhost:8501` in your browser.

## 📋 Usage Guide

### 1. Company Setup

**Navigation:** 🔍 Επιλογή → Create or Select Company

- Enter company name
- Select work model (5-day, 6-day, or 7-day week)
- Configure active shifts (Morning, Afternoon, Evening, etc.)
- Define roles (Cashier, Server, Chef, Barista, etc.)
- Set labor rules:
  - Maximum daily hours
  - Minimum rest between shifts
  - Weekly hour limits
  - Maximum consecutive work days

### 2. Employee Management

**Navigation:** 👥 Υπάλληλοι

**Adding Employees:**
1. Fill in employee name
2. Select roles (can choose multiple)
3. Define availability (which shifts they can work)
4. Click "Προσθήκη" to add

**Editing Employees:**
- Click on employee name to expand
- Modify details
- Save or delete as needed

### 3. Schedule Creation

**Navigation:** 📅 Πρόγραμμα

**Automatic Generation:**
1. Select scope (Weekly or Monthly)
2. Choose start date
3. Click "Δημιουργία"
4. System generates optimal schedule
5. Review violations and adjust if needed

**Manual Editing (Visual Builder):**
1. View weekly grid
2. Select role for each employee/shift cell
3. Click "Αποθήκευση εβδομάδας" to save
4. System validates for conflicts

**Advanced Features:**
- **Analytics**: Click "Αναλυτικά" for detailed reports
- **Export**: Download schedule as Excel or CSV
- **Import**: Upload existing schedule data
- **Calendar**: View monthly calendar with shifts
- **Auto-Fix**: Click "Επανέλεγχος & Αυτο-διόρθωση" to optimize

### 4. Shift Swaps

**Employee Request:**
1. Select requester and target employee
2. Choose date and shift
3. Submit request (status: pending)

**Manager Approval:**
1. View pending requests
2. Add notes if needed
3. Approve or reject
4. Approved swaps apply immediately

### 5. Analytics & Reports

**Available Visualizations:**
- **Hours Distribution**: Bar chart of hours per employee
- **Shift Distribution**: Pie chart of shift types
- **Timeline**: Gantt chart of shifts over time
- **Coverage Heatmap**: Staffing levels by date/shift/role
- **Workload Comparison**: Fair distribution analysis

**Export Options:**
- Excel: Multi-sheet workbook with all data
- CSV: Simple format for compatibility

## ⚙️ Configuration

### Work Models

**5-Day Week (5ήμερο)**
- Default: 8 hours/day
- Weekly limit: 40 hours
- Common in retail and services

**6-Day Week (6ήμερο)**
- Default: 9 hours/day
- Weekly limit: 48 hours
- Standard hospitality model

**7-Day Week (7ήμερο)**
- Default: 9 hours/day
- Weekly limit: 56 hours
- Continuous operations

### Labor Rules

Configurable constraints:
- `max_daily_hours_*`: Maximum hours per day by work model
- `max_daily_overtime`: Additional overtime allowed
- `min_daily_rest`: Minimum hours between shifts
- `weekly_hours_*`: Maximum weekly hours by model
- `monthly_hours`: Maximum monthly hours
- `max_consecutive_days`: Maximum days without rest

### Roles & Priorities

Each role can be configured with:
- **Priority**: 1-10 (lower = higher priority)
- **Min per shift**: Minimum staff needed
- **Max per shift**: Maximum staff allowed
- **Preferred shifts**: Which shifts this role typically works
- **Cost**: Hourly rate (for future cost analysis)

## 🏗️ Architecture

### Project Structure
```
shift_planner/
├── main.py                 # Application entry point
├── ui_pages.py            # Page components and routing
├── scheduler.py           # Scheduling algorithms
├── db.py                  # Database operations
├── constants.py           # Configuration constants
├── analytics.py           # Analytics and visualizations (NEW)
├── export_utils.py        # Export/import functionality (NEW)
├── calendar_view.py       # Calendar components (NEW)
├── notifications.py       # Notification system (NEW)
├── onboarding.py          # User onboarding (NEW)
├── requirements.txt       # Python dependencies
├── .env                   # Environment configuration
├── shifts.db             # SQLite database
└── assets/               # Images and static files
```

### Database Schema

**companies**
- id, name, active_shifts, roles, rules, role_settings, work_model, active

**employees**
- id, company_id, name, roles, availability

**schedule**
- id, company_id, employee_id, date, shift, role

**shift_swaps**
- id, company_id, requester_id, target_employee_id, date, shift, status, manager_note, created_at

### Key Technologies

- **Streamlit 1.40.0**: Modern web framework with fragments, dialogs, and popov ers
- **Plotly 5.24.0**: Interactive visualizations
- **Pandas 2.2.2**: Data manipulation
- **PuLP 2.7.0**: Mathematical optimization (optional)
- **SQLite**: Embedded database with WAL mode
- **OpenPyXL**: Excel file processing

## 🎨 Customization

### Theme

Toggle between light and dark modes in the sidebar. Custom CSS provides:
- Consistent color schemes
- Rounded corners and shadows
- Smooth transitions
- Responsive layouts

### Adding Custom Shifts

1. Go to "Επιχείρηση" page
2. Scroll to "Βάρδιες" section
3. Enter new shift name
4. Click "Προσθήκη"
5. Define time range in `constants.py` if needed:

```python
SHIFT_TIMES = {
    "Πρωί": (8, 16),
    "Απόγευμα": (16, 23),
    "Βράδυ": (23, 7),
    "Custom Shift": (10, 18)  # Add here
}
```

### Adding Custom Roles

1. Go to "Επιχείρηση" page
2. Scroll to "Ρόλοι" section
3. Enter new role name
4. Click "Προσθήκη Ρόλου"
5. Configure priority and requirements

## 🔐 Authentication (Optional)

For production deployment, enable authentication:

1. Set in `.env`:
```env
AUTH_ENABLED=true
APP_ENV=prod
```

2. Create `.streamlit/auth.yaml`:
```yaml
credentials:
  usernames:
    admin:
      name: Administrator
      password: $2b$12$... # Use bcrypt hash
cookie:
  name: shift_planner_cookie
  key: random_signature_key_here
  expiry_days: 30
```

3. Generate password hash:
```python
import streamlit_authenticator as stauth
hashed = stauth.Hasher(['your_password']).generate()
print(hashed[0])
```

## 📊 Performance Tips

1. **Use Fragments**: Most analytics components use `@st.fragment` for fast updates
2. **Database Indexing**: Ensure indexes on frequently queried columns
3. **Pagination**: For large datasets, implement pagination
4. **Caching**: Use `@st.cache_data` for expensive computations
5. **WAL Mode**: Database uses Write-Ahead Logging for better concurrency

## 🐛 Troubleshooting

### Common Issues

**"No employees to schedule"**
- Add employees before generating schedule
- Check that employees have availability set

**"Failed to initialize authentication"**
- Verify `.streamlit/auth.yaml` exists
- Check YAML syntax
- Ensure password hashes are correct

**Import errors for analytics**
- Verify all dependencies installed: `pip install -r requirements.txt`
- Check Python version (3.9+ required)

**Scheduling violations**
- Review company rules configuration
- Use "Επανέλεγχος & Αυτο-διόρθωση" feature
- Manually adjust problematic assignments

## 🚀 Deployment

### Docker (Recommended)

Use included `Dockerfile` and `docker-compose.yml`:

```bash
docker-compose up -d
```

### Streamlit Cloud

1. Push to GitHub repository
2. Connect to Streamlit Cloud
3. Configure secrets in dashboard
4. Deploy

### Manual Server

```bash
# Install dependencies
pip install -r requirements.txt

# Run with production settings
streamlit run main.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
```

## 📝 API Reference

### Scheduler Functions

```python
from scheduler import generate_schedule_v2, auto_fix_schedule, check_violations

# Generate schedule
schedule_df, missing_df = generate_schedule_v2(
    start_date=date.today(),
    employees=employee_list,
    active_shifts=["Morning", "Evening"],
    roles=["Server", "Chef"],
    rules=company_rules,
    role_settings=role_config,
    days_count=7,
    work_model="5ήμερο"
)

# Fix violations
fixed_df, violations_df = auto_fix_schedule(
    schedule_df, employees, active_shifts, roles, rules, role_settings, work_model
)

# Check compliance
violations = check_violations(schedule_df, rules, work_model)
```

### Analytics Functions

```python
from analytics import show_detailed_analytics, render_kpi_cards

# Show analytics dialog
show_detailed_analytics(schedule_df, employees, active_shifts, roles)

# Render KPI cards
render_kpi_cards(schedule_df, employees, company, violations_df)
```

### Export Functions

```python
from export_utils import export_to_excel, export_to_csv

# Export to Excel
excel_bytes = export_to_excel(schedule_df, company, employees, violations_df)

# Export to CSV
csv_bytes = export_to_csv(schedule_df)
```

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional optimization algorithms
- Mobile app integration
- Email/SMS notifications
- Advanced forecasting
- Multi-location support
- REST API layer

## 📄 License

This project is provided as-is for educational and commercial use.

## 🆘 Support

For issues, questions, or feature requests:
1. Check this documentation
2. Review in-app help system
3. Examine console logs for errors
4. Contact development team

## 🎯 Roadmap

### Planned Features
- [ ] Employee availability requests
- [ ] Automatic conflict detection
- [ ] Shift bidding system
- [ ] Mobile responsiveness improvements
- [ ] Multi-tenant support
- [ ] Advanced cost analysis
- [ ] Integration with payroll systems
- [ ] AI-powered demand forecasting
- [ ] WhatsApp/Email notifications
- [ ] Performance analytics
- [ ] Custom report builder

---

**Version**: 2.0 (Modernized with Streamlit 1.40+)
**Last Updated**: November 2025
**Maintainers**: Development Team
