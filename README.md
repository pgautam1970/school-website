# Kashyap Vidyapeeth Inaruwa - Interactive School Website

## 🎓 Overview

A modern, fully responsive school website for Kashyap Vidyapeeth Inaruwa built with vanilla HTML, CSS, and JavaScript. The website features dynamic content loading, an intelligent chat assistant, and a beautiful user interface.

## ✨ Features

### 🎯 Core Features
- **Dynamic Content Loading** - Single Page Application (SPA) style navigation
- **Responsive Design** - Fully responsive on mobile, tablet, and desktop
- **Chat Widget** - Interactive chat assistant with smart responses
- **Image Gallery** - Lightbox with keyboard navigation
- **Video Gallery** - Embedded YouTube videos
- **Contact Form** - Client-side validation
- **Event Announcements** - Modal alerts for special events
- **Marquee Banner** - Scrolling announcement banner

### 📱 Mobile-Friendly
- Hamburger menu for mobile navigation
- Touch-friendly buttons and interface
- Optimized for all screen sizes
- Adaptive layouts using CSS Grid and Flexbox

### ♿ Accessibility
- Semantic HTML
- Keyboard navigation support
- Focus styles for all interactive elements
- Alt text for all images

## 📂 File Structure

```
project/
├── index.html          # Main HTML file
├── styles.css          # Complete stylesheet
├── app.js             # JavaScript logic
├── README.md          # This file
├── assets/            # Image placeholder folder
│   ├── logo.png
│   ├── gallery1.jpg through gallery6.jpg
│   ├── team1.jpg through team4.jpg
│   └── principal.jpg
└── downloads/         # PDF documents folder
    ├── admission-form.pdf
    ├── prospectus.pdf
    ├── academic-calendar.pdf
    ├── fee-structure.pdf
    ├── code-of-conduct.pdf
    └── curriculum.pdf
```

## 🚀 Getting Started

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/pgautam1970/school-website.git
   cd school-website
   ```

2. **Add Assets**
   - Create an `assets/` folder
   - Add placeholder images for logos, gallery, team, and principal
   - Create a `downloads/` folder for PDF documents

3. **Open in Browser**
   - Simply open `index.html` in your web browser
   - No build process required!

### Hosting

You can host this website on:
- **GitHub Pages** - Free hosting
- **Netlify** - Free with easy deployment
- **Vercel** - Fast static hosting
- **Any static web host**

## 🎨 Customization

### Colors
Edit CSS variables in `styles.css`:
```css
:root {
    --primary-color: #003d7a;
    --secondary-color: #d4af37;
    --accent-color: #1e5a96;
    /* ... more variables ... */
}
```

### Content
Edit content in `app.js` in the `contentData` object:
```javascript
const contentData = {
    home: { ... },
    mission: { ... },
    // ... more pages ...
}
```

### Chat Responses
Customize chat responses in the `chatResponses` object:
```javascript
const chatResponses = {
    greeting: [ ... ],
    admission: [ ... ],
    // ... more responses ...
}
```

## 🌐 Menu Structure

- **Home** - Landing page with hero section
- **About Us**
  - Mission & Vision
  - Our Team
  - Principal's Message
- **Academics** - Curriculum overview
- **Life at KVI** - Activities and clubs
- **Gallery**
  - Image Gallery
  - Video Gallery
- **Downloads** - Documents and forms
- **Contact Us** - Contact form and map

## 💬 Chat Features

The AI-powered chat assistant understands keywords:
- **Admission** - Admission-related queries
- **Academics** - Course and curriculum questions
- **Contact** - Contact information
- **Events** - Event announcements
- **General** - Default responses

## 📊 Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)
- Mobile browsers

## 🔒 Performance

- Lightweight (no frameworks)
- Fast loading times
- Optimized images recommended
- Smooth animations
- Lazy loading ready

## 📝 Notes

- All features work without a backend
- Contact form data is not sent anywhere (client-side only)
- Add your own backend API to process form submissions
- Images are placeholders - replace with actual images

## 🛠️ Development

### No Build Process Required
This project uses vanilla HTML, CSS, and JavaScript - no build tools needed!

### Make Changes
1. Edit files directly
2. Refresh browser to see changes
3. Deploy when satisfied

## 📞 Contact

**School:** Kashyap Vidyapeeth Inaruwa  
**Location:** Inaruwa-4, Sunsari, Nepal  
**Phone:** +977-9802779301  
**Email:** kvnepal@gmail.com  

## 📄 License

This project is free to use and modify.

---

**Built with ❤️ for Education**