# 🗓️ Shift Planner Pro — Modern Employee Scheduling

[![Streamlit](https://img.shields.io/badge/Streamlit-1.40-FF4B4B.svg?style=for-the-badge&logo=Streamlit)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB.svg?style=for-the-badge&logo=Python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

A state-of-the-art employee scheduling application built with Streamlit 1.40+, featuring AI-powered schedule generation, advanced analytics, and a modern, responsive UI.

![Shift Planner Pro](https://via.placeholder.com/800x400/667eea/FFFFFF?text=Shift+Planner+Pro)

## ✨ Highlights

### 🚀 **What's New in v2.0**

- **Modern Streamlit 1.40+ Features**: Fragments, dialogs, and popover components for lightning-fast interactions
- **Advanced Analytics Dashboard**: Interactive Plotly visualizations with real-time KPIs
- **Calendar Views**: Monthly calendar and weekly timeline with intuitive navigation
- **Export/Import**: Professional Excel reports with multiple sheets
- **Smart Notifications**: Toast messages and notification center for user feedback
- **Interactive Onboarding**: Guided tour for first-time users
- **Mobile Responsive**: Fully optimized for tablets and phones
- **Dark Mode**: Beautiful light/dark theme with smooth transitions

### 🎯 Core Features

#### 🤖 **AI-Powered Scheduling**
- Automatic schedule generation respecting availability and labor laws
- MILP optimization for mathematically optimal assignments
- Auto-fix functionality to resolve violations intelligently
- Fair workload distribution with variance monitoring

#### 👥 **Employee Management**
- Comprehensive employee profiles with roles and availability
- Multi-role support with configurable priorities
- Bulk import/export capabilities
- Real-time validation

#### 📊 **Advanced Analytics**
- **Hours Distribution**: Visual breakdown of workload per employee
- **Shift Distribution**: Pie charts showing shift allocation
- **Timeline Views**: Gantt-style shift timelines
- **Coverage Heatmaps**: Role coverage analysis by date/shift
- **Workload Comparison**: Fair distribution analytics with variance tracking
- **KPI Dashboard**: Real-time metrics (shifts, hours, violations, employees)

#### 📅 **Visual Schedule Builder**
- Interactive weekly grid editor
- Drag-and-drop role assignment
- Real-time conflict detection
- Monthly calendar view with shift indicators
- Hour-by-hour timeline visualization

#### 🔄 **Shift Swaps**
- Employee-initiated swap requests
- Manager approval workflow with notes
- Automatic schedule updates upon approval
- Complete audit trail

#### 📥 **Professional Export/Import**
- **Excel**: Multi-sheet workbooks (schedule, employees, statistics, violations)
- **CSV**: Simple format for universal compatibility
- **Import Validation**: Automatic data checking
- **Template Generation**: Starter files for imports

#### 🎨 **Modern UI/UX**
- Light/Dark theme with customizable colors
- Responsive design for all devices
- Smooth animations and transitions
- Contextual help and tooltips
- Keyboard shortcuts for power users
- Progress indicators for long operations

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- pip or conda

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/shift_planner.git
cd shift_planner

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run main.py
```

Visit http://localhost:8501 in your browser!

### Quick Demo

```bash
# Use demo mode for testing (no authentication)
echo "AUTH_ENABLED=false" > .env
streamlit run main.py
```

## 📖 Documentation

📚 **[Complete Documentation](DOCUMENTATION.md)** — Comprehensive guide covering all features

### Quick Links

- [Installation Guide](DOCUMENTATION.md#-getting-started)
- [Usage Guide](DOCUMENTATION.md#-usage-guide)
- [Configuration](DOCUMENTATION.md#️-configuration)
- [API Reference](DOCUMENTATION.md#-api-reference)
- [Troubleshooting](DOCUMENTATION.md#-troubleshooting)
- [Deployment](DOCUMENTATION.md#-deployment)

## 🎯 Key Workflows

### 1️⃣ Create Your First Schedule

```
1. Select/Create Company → Configure work model and rules
2. Add Employees → Set roles and availability
3. Generate Schedule → Click "Δημιουργία" for automatic optimization
4. Review & Export → Download Excel report
```

### 2️⃣ Analyze Workload

```
1. Go to Schedule page
2. Click "Αναλυτικά" button
3. Explore visualizations:
   - Hours distribution
   - Shift breakdown
   - Timeline view
   - Coverage heatmap
```

### 3️⃣ Handle Shift Swaps

```
1. Employee submits swap request
2. Manager reviews in "Shift Swaps" section
3. Approve/Reject with notes
4. Schedule updates automatically
```

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | Streamlit 1.40.0 | Modern web framework with fragments & dialogs |
| **Visualization** | Plotly 5.24.0 | Interactive charts and graphs |
| **Data Processing** | Pandas 2.2.2 | DataFrame operations |
| **Optimization** | PuLP 2.7.0 | Mathematical optimization (optional) |
| **Database** | SQLite 3 | Embedded database with WAL mode |
| **Authentication** | streamlit-authenticator | User auth (optional) |
| **Export** | OpenPyXL 3.1.5 | Excel file generation |

## ⚙️ Configuration

### Environment Variables

Create `.env` file:

```env
# Application
APP_ENV=dev                    # dev or prod
DB_FILE=shifts.db             # Database file path
SERVER_PORT=8501              # Port number
SESSION_TTL_MIN=240           # Session timeout in minutes
TZ=Europe/Athens              # Timezone

# Logging
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR

# Authentication (optional)
AUTH_ENABLED=false            # Enable authentication
DEV_AUTH_FALLBACK=true        # Allow fallback in dev mode
```

### Work Models

- **5ήμερο** (5-day): 8h/day, 40h/week — Standard retail/services
- **6ήμερο** (6-day): 9h/day, 48h/week — Hospitality standard
- **7ήμερο** (7-day): 9h/day, 56h/week — Continuous operations

### Labor Rules

All rules are configurable per company:
- Maximum daily hours (by work model)
- Minimum rest between shifts
- Weekly hour limits
- Monthly hour caps
- Maximum consecutive work days

## 📊 Screenshots

### Dashboard & Analytics
![Analytics Dashboard](https://via.placeholder.com/600x400/764ba2/FFFFFF?text=Analytics+Dashboard)

### Visual Schedule Builder
![Schedule Builder](https://via.placeholder.com/600x400/667eea/FFFFFF?text=Visual+Builder)

### Calendar View
![Calendar View](https://via.placeholder.com/600x400/4ecdc4/FFFFFF?text=Calendar+View)

## 🐳 Docker Deployment

```bash
# Using docker-compose (recommended)
docker-compose up -d

# Or build manually
docker build -t shift-planner .
docker run -p 8501:8501 shift-planner
```

## 🧪 Development

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
# Format code
black .

# Linting
flake8 .

# Type checking
mypy .
```

### Project Structure

```
shift_planner/
├── main.py                 # Entry point
├── ui_pages.py            # UI components
├── scheduler.py           # Scheduling logic
├── db.py                  # Database layer
├── constants.py           # Configuration
├── analytics.py           # ✨ NEW: Analytics & visualizations
├── export_utils.py        # ✨ NEW: Export/import
├── calendar_view.py       # ✨ NEW: Calendar components
├── notifications.py       # ✨ NEW: Notification system
├── onboarding.py          # ✨ NEW: User onboarding
├── requirements.txt       # Dependencies
├── .env                   # Configuration
└── assets/               # Static files
```

## 🤝 Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Priorities

- [ ] Mobile app (React Native)
- [ ] REST API layer
- [ ] Email/SMS notifications
- [ ] Advanced demand forecasting
- [ ] Multi-location support
- [ ] Payroll integration
- [ ] Employee self-service portal
- [ ] Performance analytics

## 📝 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) file for details.

## 🆘 Support & Community

- 📚 [Documentation](DOCUMENTATION.md)
- 💬 [Discussions](https://github.com/yourusername/shift_planner/discussions)
- 🐛 [Issue Tracker](https://github.com/yourusername/shift_planner/issues)
- 📧 Email: support@example.com

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io) — The fastest way to build data apps
- Visualization powered by [Plotly](https://plotly.com)
- Optimization by [PuLP](https://github.com/coin-or/pulp)
- Icons from various sources

## 📈 Roadmap

### v2.1 (Q1 2026)
- [ ] Employee mobile app
- [ ] Push notifications
- [ ] Advanced reporting
- [ ] Multi-language support

### v2.2 (Q2 2026)
- [ ] API layer (REST/GraphQL)
- [ ] Webhooks
- [ ] Third-party integrations
- [ ] Advanced AI features

### v3.0 (Q3 2026)
- [ ] Multi-tenant architecture
- [ ] Enterprise features
- [ ] Advanced analytics & ML
- [ ] White-label option

---

<div align="center">

**Made with ❤️ using Streamlit**

[Report Bug](https://github.com/yourusername/shift_planner/issues) · [Request Feature](https://github.com/yourusername/shift_planner/issues) · [Documentation](DOCUMENTATION.md)

⭐ Star us on GitHub — it helps!

</div>
