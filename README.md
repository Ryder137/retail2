# BranchSynch - Retail Inventory Management System

A comprehensive Flask-based web application for managing inventory across multiple retail branches.

## Features

### User Management & Access Control

- **Role-based access control** (Owner, Manager, Staff)
- **User authentication** with secure password hashing
- **Branch-specific permissions** for staff and managers
- **Audit logging** for all user actions

### Inventory Management

- **Real-time stock monitoring** for each branch
- **Add/edit/delete inventory items** with categorization
- **Stock level updates** with user permissions
- **Minimum stock level alerts** with priority indicators
- **Multi-unit support** (pieces, kg, liters, etc.)

### Transfer Management

- **Stock transfer requests** between branches
- **Approval workflow** for managers and owners
- **Automatic stock level updates** after approval
- **Transfer history tracking** with status monitoring

### Reporting & Analytics

- **Inventory reports** with stock levels and alerts
- **Transfer reports** for the last 30 days
- **Downloadable reports** in CSV and JSON formats
- **Branch-specific filtering** for targeted analysis

### Dashboard & Alerts

- **Comprehensive dashboard** with key metrics
- **Low stock alerts** with priority levels
- **Recent activity feed** showing user actions
- **Quick action buttons** for common tasks

## Technology Stack

- **Backend**: Python Flask with SQLite database
- **Frontend**: HTML5, CSS3, JavaScript
- **Styling**: Tailwind CSS (CDN)
- **Icons**: Bootstrap Icons
- **Authentication**: Werkzeug security

## Installation & Setup

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Installation Steps

1. **Clone or download the project files** to your desired directory:

   ```
   c:\Users\Alliyah Angela\retail2\
   ```

2. **Navigate to the project directory**:

   ```bash
   cd "c:\Users\Alliyah Angela\retail2"
   ```

3. **Create a virtual environment** (recommended):

   ```bash
   python -m venv inventory_env
   ```

4. **Activate the virtual environment**:

   **Windows:**

   ```bash
   inventory_env\Scripts\activate
   ```

   **macOS/Linux:**

   ```bash
   source inventory_env/bin/activate
   ```

5. **Install required dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

6. **Run the application**:

   ```bash
   python app.py
   ```

7. **Access the application**:
   Open your web browser and go to: `http://127.0.0.1:5000`

## Default Login Credentials

- **Username**: admin
- **Password**: admin123
- **Role**: Owner (full access)

## System Architecture

### Database Schema

The system uses SQLite with the following main tables:

- `users` - User accounts and authentication
- `branches` - Store locations and information
- `items` - Product catalog with categories
- `inventory` - Stock levels per item per branch
- `transfer_requests` - Inter-branch transfer requests
- `audit_logs` - System activity tracking

### User Roles & Permissions

#### Owner

- Full system access
- User management capabilities
- All branch access
- Complete reporting access
- Transfer approval authority

#### Manager

- Branch-specific management
- Inventory control for assigned branch
- Transfer approval for branch transfers
- Branch-specific reporting
- Staff oversight

#### Staff

- View inventory for assigned branch
- Update stock levels
- Request transfers
- Basic reporting access
- Read-only access to other features

## Key Features in Detail

### Inventory Tracking

- Real-time stock levels across all branches
- Automatic low stock alerts when items fall below minimum levels
- Support for multiple units of measurement
- Category-based organization

### Transfer Workflow

1. Staff/Manager requests transfer between branches
2. System checks stock availability
3. Manager/Owner approves or rejects request
4. Upon approval, stock levels are automatically updated
5. Complete audit trail is maintained

### Reporting System

- Generate comprehensive inventory reports
- Transfer activity reports with filtering
- Export data in CSV or JSON formats
- Branch-specific or system-wide reporting

### Security Features

- Secure password hashing using Werkzeug
- Role-based access control
- Session management
- Audit logging for compliance

## Customization

### Adding New Item Categories

Edit the category options in `templates/add_item.html` and `templates/edit_item.html`

### Adding New Units of Measurement

Modify the unit options in the item management templates

### Customizing Alerts

Adjust the low stock alert logic in the `low_stock_alerts` route

### Styling Changes

The application uses Tailwind CSS classes. Modify the templates to change the appearance.

## Troubleshooting

### Common Issues

1. **Database not found error**: The database is automatically created on first run. Ensure write permissions in the project directory.

2. **Template not found error**: Ensure all template files are in the `templates/` directory.

3. **Permission denied errors**: Run the application with appropriate user permissions.

4. **Port already in use**: Change the port in `app.py` by modifying the `app.run()` call.

### Support

For technical issues or questions about the system, check the code comments and database schema for implementation details.

## Future Enhancements

Potential improvements that could be added:

- Barcode scanning integration
- Email notifications for low stock
- Advanced analytics and charts
- Multi-currency support
- Supplier management
- Purchase order generation
- Mobile responsive improvements
- REST API for integrations

## License

This project is created for educational and business use. Modify and adapt as needed for your specific requirements.
