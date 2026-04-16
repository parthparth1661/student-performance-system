-- 🎯 Student Performance Data Analysis System (SPDA) - Standardized Schema
-- Optimized for Flask + MySQL + Student Panel Integration

-- 1️⃣ Database Strategy
CREATE DATABASE IF NOT EXISTS SPDA;
USE SPDA;

-- 2️⃣ Admin Identity Module
CREATE TABLE IF NOT EXISTS admin (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
);

-- 3️⃣ Student Registry Module
CREATE TABLE IF NOT EXISTS students (
    enrollment_no VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    department VARCHAR(50),
    semester INT,
    password_hash VARCHAR(255),
    is_password_changed BOOLEAN DEFAULT FALSE,
    phone VARCHAR(20),
    contact_no VARCHAR(15),
    profile_pic VARCHAR(255) DEFAULT 'default.png'
);

-- 4️⃣ Faculty & Curriculum Module
CREATE TABLE IF NOT EXISTS faculty (
    faculty_id INT AUTO_INCREMENT PRIMARY KEY,
    faculty_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    department VARCHAR(50),
    password_hash VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    semester INT,
    faculty_id INT,
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE SET NULL
);

-- 5️⃣ Academic Performance Module
CREATE TABLE IF NOT EXISTS marks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    subject_id INT,
    internal_marks INT DEFAULT 0,
    viva_marks INT DEFAULT 0,
    external_marks INT DEFAULT 0,
    total_marks INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);

-- 6️⃣ Institutional Attendance Module
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    subject_id INT,
    date DATE,
    status VARCHAR(20),
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);

-- 7️⃣ Student Engagement Module (Feedback Hub)
CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(50),
    subject VARCHAR(255),
    message TEXT,
    type VARCHAR(50),
    status VARCHAR(50),
    admin_reply TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE
);
