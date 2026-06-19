# SMARTHAND/REHAB

### Intelligent Hand Rehabilitation Monitoring and Tracking System

##  Overview

This project consists of the development of a hand rehabilitation system based on flex sensors, capable of measuring finger movements in real time, calculating clinical metrics such as **Range of Motion (ROM)**, and counting repetitions performed during therapeutic sessions.

The system integrates embedded hardware, local visualization, remote storage, and Telegram-based consultation, enabling continuous monitoring of the rehabilitation process.

---

##  Project Objectives

* Measure finger flexion using flex sensors.
* Estimate joint angles for each monitored finger.
* Calculate the Range of Motion (ROM) achieved during rehabilitation sessions.
* Count therapeutic repetitions automatically.
* Visualize rehabilitation metrics in real time.
* Store session history in the cloud.
* Enable remote consultation through Telegram.
* Facilitate patient progress tracking.

---

#  System Architecture

```text
Flex Sensors
      │
      ▼
    ESP32
      │
      ▼
 Desktop Application (Python)
      │
      ▼
    n8n Webhook
      │
      ▼
  Google Sheets
      │
      ├────────► Session History
      │
      ▼
 Telegram Bot
      │
      ▼
 Remote Queries
```

---

#  System Components

## Hardware

### Microcontroller

* ESP32

### Sensors

* 3 Flex Sensors:

  * Thumb
  * Index Finger
  * Ring Finger

### Local Visualization

* OLED Display

### Power Supply

* 5V USB Power Supply

---

## Software

### Embedded Firmware

Developed for ESP32.

Main functions:

* Flex sensor acquisition
* Angle estimation
* ROM calculation
* Repetition counting
* Serial communication
* Session management

---

### Desktop Application

Developed in Python.

#### Libraries Used

```python
tkinter
matplotlib
numpy
pyserial
requests
```

#### Main Features

* Patient registration
* Session start and stop
* Real-time visualization
* Clinical metric calculation
* Session summary generation
* Data transmission to n8n

---

#  Graphical User Interface

The desktop application provides:

### Patient Registration

* Patient name registration

### Session Management

* Start rehabilitation session
* End rehabilitation session

### Real-Time Monitoring

For each monitored finger:

* Current angle
* Current ROM
* Time evolution

### Session Summary

At the end of each session, the system calculates:

* Session duration
* Maximum ROM per finger
* Repetitions per finger
* Average ROM
* Total repetitions

---

#  OLED Display

An OLED module was implemented to provide direct feedback to the user.

Displayed information includes:

* System status
* Monitored finger
* Rehabilitation variables
* Immediate user feedback

---

#  Remote Storage System

The project uses **n8n** to automate rehabilitation data storage.

## Storage Workflow

```text
Python Application
        │
        ▼
    n8n Webhook
        │
        ▼
   Google Sheets
```

Each rehabilitation session stores:

| Field             | Description          |
| ----------------- | -------------------- |
| Patient           | Patient name         |
| Date              | Session date         |
| Duration          | Session duration     |
| D1_ROM            | Finger 1 ROM         |
| D1_Reps           | Finger 1 repetitions |
| D2_ROM            | Finger 2 ROM         |
| D2_Reps           | Finger 2 repetitions |
| D3_ROM            | Finger 3 ROM         |
| D3_Reps           | Finger 3 repetitions |
| Average_ROM       | Average ROM          |
| Total_Repetitions | Total repetitions    |
| Summary           | Session summary      |

---

#  Remote Consultation System

A Telegram Bot integrated with n8n was developed to allow users to access rehabilitation records remotely.

## Consultation Workflow

```text
User
   │
   ▼
Telegram
   │
   ▼
n8n
   │
   ▼
Google Sheets
   │
   ▼
Response to User
```

---

## Available Commands

### Latest Session

```text
/last PatientName
```

Example:

```text
/last SaraMarin
```

Response:

```text
Patient: Sara Marin

Latest Session

Date: 2026-06-15
Duration: 15 min

Finger 1
ROM: 82°
Repetitions: 24

Finger 2
ROM: 76°
Repetitions: 21

Finger 3
ROM: 80°
Repetitions: 18

Average ROM: 79°
Total Repetitions: 63
```

---

### Session History

```text
/history PatientName
```

Example:

```text
/history SaraMarin
```

Response:

```text
Sara Marin - Rehabilitation History

Session 1 → Average ROM 65°
Session 2 → Average ROM 70°
Session 3 → Average ROM 74°
Session 4 → Average ROM 77°
Session 5 → Average ROM 80°

Trend:
Progressive Improvement
```

---

#  Monitored Clinical Variables

## Joint Angle

Instantaneous finger flexion angle.

**Unit:** Degrees (°)

---

## Range of Motion (ROM)

Difference between the maximum and minimum angle reached during a rehabilitation session.

```text
ROM = Maximum Angle − Minimum Angle
```

**Unit:** Degrees (°)

---

## Repetitions

Number of flexion-extension cycles completed during a rehabilitation session.

---

#  Achieved Results

The developed system enables:

* Real-time acquisition of finger flexion data.
* Automatic ROM calculation.
* Automatic therapeutic repetition counting.
* Local visualization through both a desktop interface and OLED display.
* Automatic session storage in Google Sheets.
* Remote access to rehabilitation data through Telegram.
* Long-term patient progress monitoring.

---

#  Project Structure

```text
HandRehabSystem/

│
├── ESP32/
│   └── main.py
│
├── Desktop_App/
│   ├── tkinter_monitor_collector.py
│   └── monitor.exe
│
├── n8n/
│   ├── webhook_sheets_workflow.json
│   └── telegram_query_workflow.json
│
│
└── README.md
```

---

#  Future Improvements

* Web dashboard for therapists.
* Automatic PDF report generation.
* Additional sensors for full-hand monitoring.
* Mobile application.
* Advanced rehabilitation analytics.
* Integration with electronic health records.
* Real-time telerehabilitation capabilities.

---

#  Developers

**Sara Marín**

**Juan Felipe Vanegas**

**Leon Arboleda**
Biomedical Engineering Students
Instituto Tecnológico Metropolitano (ITM)

---

# License

This project was developed for academic and research purposes in the field of technology-assisted rehabilitation.
