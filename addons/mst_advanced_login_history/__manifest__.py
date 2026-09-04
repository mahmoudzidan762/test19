# -*- coding: utf-8 -*-
{
    "name": "Advanced User Audit Log and Login History",
    "summary": "Odoo 19 Login History, User Activity Audit, Advanced Logs, Model Logs, Session and Location Monitoring",

    "description": """
        Advanced  User Audit Log and Login History
        ======================
        
        Overview
        --------
        Advanced Login History is an Odoo 19 module that helps administrators monitor user login sessions, failed login attempts, logout history, user activity logs, model-wise logs, browser, device, IP address, and location tracking.
        
        This module improves Odoo security visibility by recording every user session and important user activity with useful audit details such as login time, logout time, session duration, browser, operating system, IP address, country, city, latitude, longitude, model name, record name, action type, and before/after changes.
        
        Features
        --------
        - Track user login history
        - Track user logout history
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
        - Dashboard for login activity summary
        - Recent activity panel for quick monitoring
        - Advanced Logs for all user activity logs
        - Model Logs for configured model-based activity logs
        - Configuration menu to select models for model-wise tracking
        - Track create, modify, and delete operations
        - Capture changed field values with old and new values
        - Open related records directly from logs
        - Show sessions and activity logs inside user form
        - Kill all active sessions from user form
        - Admin-friendly access monitoring
        - Fully compatible with Odoo 19
        
        Benefits
        --------
        - Improves Odoo login security monitoring
        - Helps administrators track user access activity
        - Identifies failed login attempts and suspicious access
        - Maintains clear login and logout audit history
        - Provides visibility of IP address, browser, device, and location
        - Helps review active user sessions
        - Tracks record-level user activities
        - Helps monitor important models like Sale Orders, Purchase Orders, Products, Employees, Customers, Vendors, and Invoices
        - Supports internal audit and compliance needs
        - Improves control over Odoo user access
        """,

    "author": "MindSpark Technologies",
    "website": "https://mindsparktechnologies.com",
    "maintainer": "MindSpark Technologies",
    "category": "Administration",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",

    "depends": [
        "base",
        "web",
    ],

    "data": [
        "security/ir.model.access.csv",
        "views/login_history_views.xml",
        "views/user_activity_audit_views.xml",
        "views/activity_log_config_views.xml",
        "views/login_history_dashboard_menu.xml",
    ],

    "assets": {
        "web.assets_backend": [
            "mst_advanced_login_history/static/src/js/session_tracker.js",
            "mst_advanced_login_history/static/src/js/login_history_dashboard.js",
            "mst_advanced_login_history/static/src/xml/login_history_dashboard.xml",
            "mst_advanced_login_history/static/src/scss/login_history_dashboard.scss",
        ],
        "web.assets_frontend": [
            "mst_advanced_login_history/static/src/js/login_location.js",
        ],
    },

    "images": [
        "static/description/banner.png",
    ],

    "installable": True,
    "application": True,
    "auto_install": False,
}