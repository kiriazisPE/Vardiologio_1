# Shift Plus Pro 🚀

An advanced AI-powered employee scheduling application that creates optimal work schedules using hybrid algorithms (AI + MILP + Greedy). Features comprehensive workforce management, role-based scheduling, and intelligent assignment optimization.

## 🌟 Live Demo
**[View Live Application on Streamlit Cloud](https://your-app-name.streamlit.app/)**

## ✨ Key Features
- 🤖 **AI-Enhanced Scheduling**: Powered by OpenAI for intelligent assignments
- 📊 **Hybrid Algorithms**: AI + MILP + Greedy for optimal results  
- 👥 **Employee Management**: Roles, availability, importance ratings
- 📅 **Flexible Shifts**: Day/night scheduling with role requirements
- 📈 **Analytics Dashboard**: Performance metrics and insights
- 💾 **Data Export**: CSV export for external systems

## Quick Start

## 🚀 Deployment Options

### Option 1: Streamlit Cloud (Recommended)
1. **Fork this repository** to your GitHub account
2. **Go to [Streamlit Cloud](https://share.streamlit.io/)**
3. **Connect GitHub** and select your forked repository
4. **Set main file**: `shift_plus.py`
5. **Add secrets** in Streamlit dashboard:
   ```toml
   AI_API_KEY = "your-openai-api-key-here"
   OPENAI_API_KEY = "your-openai-api-key-here"
   ```
6. **Deploy** and share your live app!

### Option 2: Local Development
```bash
# Clone repository
git clone https://github.com/yourusername/shift-plus-pro.git
cd shift-plus-pro

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your OpenAI API key

# Run application
streamlit run shift_plus.py
streamlit run shift_plus_clean.py
```


## Features 🌟

### Core Scheduling
- **AI-Driven Algorithm**: Automatically assigns shifts based on availability and preferences
- **Constraint Handling**: Respects rest hours, maximum consecutive days, and hour limits
- **Role Coverage**: Ensures required positions are filled for each shift
- **No Cost Logic**: All cost, wage, and budget features have been removed for clarity and compliance

---

See `PRODUCTION_SCOPE.md` for the full production scope and design summary.

### AI-Powered Enhancement
- **OpenAI Integration**: Uses GPT models for schedule optimization
- **Context-Aware**: Considers employee satisfaction and business efficiency
- **Flexible Requirements**: Handles complex business rules and special situations

### User-Friendly Interface
- **Dashboard**: Quick overview of employees, schedules, and key metrics
- **Business Settings**: Configure your operation parameters and shift structure
- **Employee Management**: Easy add, edit, and manage staff with full availability tracking
- **Schedule Generator**: Create schedules with one click, preview and adjust as needed
- **Custom Requirements**: Handle special events, holidays, and unique staffing needs

### Data Management
- **SQLite Database**: Reliable local data storage with backup capability
- **Import/Export**: Schedule data portability for payroll integration
- **History Tracking**: Maintain records of past schedules and changes
- **Data Validation**: Prevents conflicts and ensures schedule integrity

## Use Cases 📋

### Small Businesses
- **Restaurants**: Handle busy periods with appropriate staffing levels
- **Retail Stores**: Balance customer service with labor costs
- **Coffee Shops**: Manage peak hours and specialized roles (baristas, cashiers)
- **Healthcare Clinics**: Ensure coverage for patient care and administrative needs

### Service Industries  
- **Cleaning Services**: Coordinate teams across multiple locations
- **Security Companies**: Maintain 24/7 coverage with qualified personnel
- **Customer Support**: Balance call volume with agent availability
- **Delivery Services**: Match driver schedules with demand patterns

### Event Management
- **Conferences**: Staff registration, setup, and breakdown efficiently
- **Weddings**: Coordinate multiple service roles throughout event timeline
- **Trade Shows**: Handle variable staffing needs across event days
- **Festivals**: Manage large teams with diverse responsibilities

## Sample Data 📊

The application includes realistic test data for a coffee shop scenario:

### Downtown Coffee Co. Demo
- **12 Diverse Employees**: Managers, baristas, cashiers, bakers, and cleaners
- **Realistic Constraints**: Part-time availability, role specializations, cost variations
- **Special Events**: Weekend rushes, coffee cupping events, reduced Sunday hours
- **2-Week Planning**: Complete scheduling scenario ready for testing

### Employee Profiles Include
- **Availability Patterns**: Weekends only, weekdays, full-time, student schedules
- **Role Specializations**: Management certification, specialized equipment training
- **Cost Considerations**: Different hourly rates reflecting experience and responsibility
- **Preference Diversity**: Day shift preference, night owls, flexible workers

## Configuration Guide ⚙️

### Business Settings
```yaml
Planning Period: 1-4 weeks (14 days recommended)
Day Shift: 6:00 AM - 2:00 PM (8 hours)
Night Shift: 2:00 PM - 10:00 PM (8 hours)
Rest Hours: 10 hours minimum between shifts
Max Consecutive Days: 5 days maximum
Weekly Hour Limits: 16-40 hours per employee
```

### Role Coverage Example
```yaml
Manager: 1 day shift, 1 night shift required
Barista: 3 day shift, 2 night shift required  
Cashier: 2 day shift, 1 night shift required
Baker: 1 day shift, 0 night shift (early morning prep)
Cleaner: 0 day shift, 1 night shift (after hours)
```

### Custom Requirements
- **Date-Specific**: Extra staff for known busy periods
- **Event-Based**: Special coverage for training, inventory, or promotions
- **Seasonal**: Reduced hours during slow periods
- **Emergency**: Last-minute coverage adjustments

## Technical Architecture 🏗️

### Core Components
- **shift_plus_core.py**: Business logic and database operations
- **shift_plus_clean.py**: Streamlit web application interface
- **common/business_settings.py**: Configuration management system
- **shift_maker.sqlite3**: Local SQLite database for data persistence

### Dependencies
```python
streamlit>=1.28.0      # Web application framework
pandas>=2.0.0          # Data manipulation and analysis  
openai>=0.28.0         # AI integration (optional)
python-dotenv>=1.0.0   # Environment variable management
```

### Database Schema
```sql
business_settings      # Core business configuration
employees             # Staff profiles and availability
schedules             # Generated shift assignments
shift_customizations  # Special requirements and exceptions
```

## Troubleshooting 🔧

### Common Issues

**Application won't start**
- Ensure Python 3.8+ is installed: `python --version`
- Install dependencies: `pip install -r requirements.txt`
- Check if port 8501 is available (close other Streamlit apps)

**Schedule generation fails**  
- Verify enough employees are available for coverage requirements
- Check that role coverage numbers are realistic for your staff
- Ensure employee hour limits allow for necessary coverage
- Review custom requirements for impossible conflicts

**AI features not working**
- Set OpenAI API key: Create `.env` file with `OPENAI_API_KEY=your_key`
- Verify internet connection for API access
- Check OpenAI account has sufficient API credits
- Try non-AI generation first to isolate the issue

**Performance is slow**
- Reduce planning period length (try 1 week instead of 2-4)
- Simplify custom requirements and business rules
- Close other applications to free system memory
- Consider upgrading hardware for large workforces (50+ employees)

### Error Messages

**"No employees available"**
- Add employees with appropriate availability for your shift times
- Check that employee availability matches your planning days

**"Coverage requirements too high"**  
- Reduce required staff count for specific roles and shifts
- Add more employees or increase their available hours

**"Database connection failed"**
- Ensure write permissions in application directory  
- Check disk space availability
- Restart application to reset database connections

## Support & Development 💬

### Getting Help
- **User Guide**: See `USER_TESTING_GUIDE.md` for comprehensive testing scenarios
- **Sample Data**: Run `setup_sample_data.py` for realistic demo environment
- **Documentation**: Code comments explain business logic and edge cases

### Contributing
- **Bug Reports**: Include steps to reproduce, expected vs. actual results
- **Feature Requests**: Describe business need and proposed solution
- **Code Contributions**: Follow existing patterns, add tests for new features

### Customization
- **Business Rules**: Modify constraint logic in `shift_plus_core.py`
- **UI Changes**: Adjust interface elements in `shift_plus_clean.py`  
- **Database Schema**: Extend tables for additional business requirements
- **AI Prompts**: Customize OpenAI requests for specific optimization criteria

## License & Credits 📄

This project is designed for small business scheduling optimization. Built with Streamlit for rapid deployment and SQLite for reliable data management.

**Technologies Used:**
- **Streamlit**: Web application framework
- **pandas**: Data manipulation and analysis
- **SQLite**: Local database storage
- **OpenAI GPT**: AI-powered schedule optimization
- **Python**: Core programming language

---

**Ready to optimize your employee scheduling?** 🎯  
Start with `python setup_sample_data.py` then `start_shift_plus.bat` and explore the coffee shop demo!# Force refresh: 10/06/2025 14:41:15
