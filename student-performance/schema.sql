-- 🎯 Student Performance Data Analysis System (SPDA) - Unified Schema
-- Final Normalized Version (Matches implementation logic)

CREATE DATABASE IF NOT EXISTS SPDA;
USE SPDA;

-- 👤 Administrative Nexus
CREATE TABLE IF NOT EXISTS admin (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
);

-- 🧑🎓 Student Registry 
CREATE TABLE IF NOT EXISTS students (
    enrollment_no VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    department VARCHAR(50),
    semester INT,
    password_hash VARCHAR(255),
    is_password_changed BOOLEAN DEFAULT FALSE,
    contact_no VARCHAR(15),
    profile_pic VARCHAR(255) DEFAULT 'default.png'
);

-- 🧑🏫 Faculty Hub
CREATE TABLE IF NOT EXISTS faculty (
    faculty_id INT AUTO_INCREMENT PRIMARY KEY,
    faculty_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    department VARCHAR(50),
    contact_no VARCHAR(20)
);

-- 📚 Curriculum Modules
CREATE TABLE IF NOT EXISTS subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    semester INT,
    faculty_id INT,
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE SET NULL
);

-- 📊 Academic Performance Ledger
CREATE TABLE IF NOT EXISTS marks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    subject_id INT,
    internal_marks INT DEFAULT 0,
    viva_marks INT DEFAULT 0,
    external_marks INT DEFAULT 0,
    total_marks INT DEFAULT 0,
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,
    UNIQUE KEY unique_student_subject (enrollment_no, subject_id)
);

-- 📅 Global Attendance Registry
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    subject_id INT,
    date DATE,
    status VARCHAR(20),
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);

-- 💬 Institutional Feedback Channel
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50),
    student_name VARCHAR(100),
    department VARCHAR(50),
    semester INT,
    subject VARCHAR(255),
    feedback_type VARCHAR(50) DEFAULT 'Suggestion',
    comment TEXT,
    admin_reply TEXT,
    status VARCHAR(20) DEFAULT 'Pending',
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rating INT DEFAULT 5,
    FOREIGN KEY (student_id) REFERENCES students(enrollment_no) ON DELETE CASCADE
);
