CREATE DATABASE IF NOT EXISTS attendance_system;
USE attendance_system;

CREATE TABLE employees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(100)
);

CREATE TABLE attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id VARCHAR(10),
    date DATE,
    sign_in TIME,
    sign_out TIME,
    status ENUM('Present', 'Late', 'Absent'),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);
