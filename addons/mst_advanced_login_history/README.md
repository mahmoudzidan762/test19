Advanced User Audit Log and Login History
======================

Overview
--------
Advanced User Audit Log and Login History is an Odoo 19 module that helps administrators monitor user access, login sessions, failed login attempts, logout history, user activity logs, model-wise audit logs, browser details, device information, IP address, and location tracking.

This module improves Odoo security visibility by recording every user session with useful audit details such as login time, logout time, session duration, browser, operating system, IP address, country, city, latitude, longitude, and map location.

It also provides advanced user activity tracking. Administrators can track create, modify, and delete operations performed by users on different Odoo records such as Sale Orders, Purchase Orders, Products, Customers, Vendors, Employees, Invoices, and other configured models.

The module includes a clean dashboard to quickly check total logins, successful logins, failed login attempts, active users, recent login activities, and latest login location. It also includes Advanced Logs, Model Logs, model configuration, session tracking, and user form session visibility.

Features
--------
- Track user login history in Odoo
- Track user logout history in Odoo
- Track failed login attempts
- Capture login time and logout time
- Calculate user session duration
- Capture IP address details
- Capture browser information
- Capture operating system and device details
- Track browser-based login location
- Track IP-based geo location
- Store country, region, city, latitude, and longitude
- View login location on Google Maps
- Display country flag in dashboard
- Display browser and operating system icons
- Dashboard for login activity summary
- Recent activity panel for quick monitoring
- Separate menu for login logs
- Separate menu for failed login logs
- Advanced Logs menu to track all user activities
- Model Logs menu to show only configured model activities
- Configuration menu to select models for model-wise tracking
- Track create, modify, and delete operations
- Capture field-level changes with old and new values
- Track changes made in important records
- Track activity for Sale Orders, Purchase Orders, Products, Customers, Vendors, Employees, Invoices, and other models
- Open related records directly from activity logs
- View session details directly from the user form
- View user activity logs directly from the user form
- Kill all active user sessions from the user form
- Admin-friendly access monitoring
- Fully compatible with Odoo 19 Community and Enterprise

Benefits
--------
- Improves Odoo login security monitoring
- Helps administrators track user access activity
- Identifies failed login attempts and suspicious access
- Maintains clear login and logout audit history
- Provides visibility of IP address, browser, device, and location
- Helps review active user sessions
- Tracks record-level user activities
- Shows what was changed before and after modification
- Helps monitor important business records
- Reduces manual checking of server logs
- Supports internal audit and compliance needs
- Improves control over Odoo user access
- Helps administrators review user actions quickly
- Useful for companies with multiple Odoo users
- Helps trace user operations with session details
- Easy-to-use security and audit tracking module

Use Cases
---------
- Companies that need Odoo user login tracking
- Administrators who want to monitor user access
- Businesses that need failed login attempt tracking
- Organizations that require login audit history
- Teams working with multiple internal Odoo users
- Companies that want to review login location and IP details
- Businesses looking for simple Odoo security monitoring
- Odoo administrators who want dashboard-based login visibility
- Companies that need user activity audit logs
- Businesses that want to track record create, update, and delete actions
- Teams that need to monitor changes in Sale Orders, Purchase Orders, Products, Employees, Customers, Vendors, and Invoices
- Organizations that need model-wise audit tracking
- Administrators who want to trace user activity by session

Installation
------------
1. Copy the module to your Odoo addons directory.
2. Restart the Odoo server.
3. Update the Apps list.
4. Search for Advanced Login History.
5. Install the module from the Apps menu.

Configuration
-------------
- Install the module.
- Open the Advanced Login History menu.
- Go to Dashboard to view login activity summary.
- Go to Login Logs to view successful login and logout records.
- Go to Failed Login Logs to view failed login attempts.
- Go to Advanced Logs to view all user activity logs.
- Go to Model Logs to view logs only for configured models.
- Go to Configuration and select the models that need separate model-wise tracking.
- Allow browser location permission to capture accurate login location.

Usage
-----
- When a user logs in, the module automatically creates a login history record.
- When a user logs out, the module updates the logout time and session duration.
- When login fails, the module records the failed login attempt.
- When a user creates, modifies, or deletes a record, the module captures the activity in Advanced Logs.
- If the model is configured in the configuration menu, the same activity is also shown in Model Logs.
- Administrators can view all login details from the dashboard and log menus.
- Administrators can open related records directly from the activity log.
- Administrators can review old and new values from the change log.
- Location records can be opened in Google Maps for quick review.
- User sessions and activity logs can be viewed from the user form.
- Administrators can kill all active sessions of a user from the user form.

Technical Details
-----------------
- Module Type: Odoo Custom Module
- Compatible with Odoo 19 Community and Enterprise
- Depends on:
  * base
  * web
- Uses browser geolocation API for location tracking
- Uses IP-based geo location fallback
- Uses Odoo backend assets for dashboard view
- Uses Odoo frontend assets for login page location capture
- Includes login history and failed login history models
- Includes user activity audit log model
- Includes activity log line model for old and new values
- Includes model log configuration
- Includes dashboard client action for login activity monitoring
- Supports session tracking
- Supports model-wise activity filtering
- Supports direct record opening from logs

Keywords
--------
odoo login history
odoo advanced login history
odoo 19 login history
free odoo login history module
odoo login tracking
odoo logout tracking
odoo failed login tracking
odoo failed login attempts
odoo user login tracking
odoo user activity tracking
odoo login audit
odoo security monitoring
odoo login location tracking
odoo ip address tracking
odoo browser tracking
odoo device tracking
odoo session tracking
odoo map location tracking
odoo login dashboard
odoo login logs
odoo user access history
odoo access monitoring
odoo admin security module
odoo 19 security module
odoo free security module
odoo login logout report
odoo user session history
odoo browser location history
odoo google map login location
odoo community login tracking
odoo enterprise login tracking
odoo activity logs
odoo advanced logs
odoo model logs
odoo user audit logs
odoo record change tracking
odoo old and new value tracking
odoo create write delete tracking
odoo sale order audit log
odoo purchase order audit log
odoo product audit log
odoo employee audit log
odoo customer activity tracking
odoo vendor activity tracking
odoo invoice activity log
odoo session management
odoo kill user sessions
odoo user activity dashboard
odoo audit trail module

Author
------
Mind Spark Technologies

Website
-------
https://mindsparktechnologies.com

License
-------
LGPL-3

Support
-------
For support, contact:
info@mindsparktechnologies.com