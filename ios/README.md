# SFCrime iOS App

A Citizen-style live crime map for San Francisco built with SwiftUI.

## Requirements

- Xcode 15.0+
- iOS 17.0+
- Swift 5.9+

## Setup

### 1. Create Xcode Project

1. Open Xcode
2. Create a new iOS App project:
   - Product Name: `SFCrime`
   - Team: Your team
   - Organization Identifier: Your identifier
   - Interface: SwiftUI
   - Language: Swift
   - Storage: SwiftData

3. Set deployment target to iOS 17.0

### 2. Copy Source Files

Copy all the Swift files from `SFCrime/` into your Xcode project, maintaining the folder structure:

```
SFCrime/
├── SFCrimeApp.swift
├── ContentView.swift
├── Domain/
│   └── Models/
│       ├── DispatchCall.swift
│       ├── IncidentReport.swift
│       ├── Priority.swift
│       └── District.swift
├── Data/
│   ├── Network/
│   │   └── APIClient.swift
│   ├── Repositories/
│   └── Cache/
│       ├── CachedDispatchCall.swift
│       └── CachedIncidentReport.swift
├── Presentation/
│   ├── Map/
│   │   ├── MapContainerView.swift
│   │   ├── CrimeMapView.swift
│   │   └── FilterSheetView.swift
│   ├── List/
│   │   └── CallListView.swift
│   ├── Detail/
│   │   └── CallDetailView.swift
│   ├── Archive/
│   │   └── ArchiveView.swift
│   └── Settings/
│       └── SettingsView.swift
└── Core/
    ├── LocationManager.swift
    └── Extensions/
```

### 3. Configure Info.plist

Add the following keys to your Info.plist:

```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>SFCrime uses your location to show nearby incidents on the map.</string>
```

### 4. Configure API URL

In `APIClient.swift`, update the base URL to point to your backend:

```swift
private let baseURL: URL = URL(string: "http://localhost:8000")!  // Development
// private let baseURL: URL = URL(string: "https://api.sfcrime.app")!  // Production
```

## Architecture

The app follows Clean Architecture with MVVM:

- **Domain Layer**: Models and use cases
- **Data Layer**: Network client, repositories, and caching
- **Presentation Layer**: SwiftUI views and view models

## Features

### Map View
- Live crime markers with priority-based colors
- Viewport-based data loading
- User location centering
- Filter by priority and time range

### List View
- Chronologically sorted dispatch calls
- Pull-to-refresh
- Cursor-based pagination
- "Data as of" timestamp

### Archive
- Search historical incidents (2018-present)
- Filter by date range, district, category
- Infinite scroll pagination

### Settings
- API health status
- Cache management
- Legal information

## Dependencies

No external dependencies required. The app uses native frameworks:
- SwiftUI
- MapKit
- SwiftData
- CoreLocation

## Testing

Run tests in Xcode:

```bash
# Unit tests
cmd+U

# Or from command line
xcodebuild test -scheme SFCrime -destination 'platform=iOS Simulator,name=iPhone 15'
```

## Building

```bash
# Debug build
xcodebuild -scheme SFCrime -configuration Debug

# Release build
xcodebuild -scheme SFCrime -configuration Release
```
