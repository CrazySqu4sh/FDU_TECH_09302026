import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
// tailwind.css also brings in the app's original styles (styles.css), layered below Tailwind utilities
import './tailwind.css'

createRoot(document.getElementById('root')).render(<App />)
