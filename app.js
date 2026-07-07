// ============================================
// KASHYAP VIDYAPEETH INARUWA - JAVASCRIPT
// Dynamic Content Loading & Chat Feature
// ============================================

// Content data for different sections
const contentData = {
    home: {
        title: 'Welcome to Kashyap Vidyapeeth Inaruwa',
        html: `
            <div class="section hero">
                <div class="hero-content">
                    <h2>Welcome to Kashyap Vidyapeeth Inaruwa</h2>
                    <p>Building Bright Futures Through Quality Education</p>
                    <div class="hero-buttons">
                        <button class="btn btn-primary" onclick="loadContent('contact')">Contact Us</button>
                        <button class="btn btn-secondary" onclick="loadContent('academics')">Explore Academics</button>
                    </div>
                </div>
            </div>
            <div class="marquee-section">
                <div class="marquee">🎉 Annual Sports Day 2026 - March 15th 🎉 | 📚 Admission Open for Academic Year 2026-27 📚 | 🌟 New STEM Lab Opening Soon 🌟</div>
            </div>
        `
    },
    mission: {
        title: 'Mission & Vision',
        html: `
            <div class="section about-section">
                <div class="container">
                    <h2 class="section-title">Mission & Vision</h2>
                    <div class="mission-vision-grid">
                        <div class="mission-card">
                            <h4>Our Mission</h4>
                            <p>To provide quality education that develops students into responsible, compassionate, and intellectually capable individuals who can contribute positively to society. We are committed to fostering an environment where every student can discover their potential and excel academically and personally.</p>
                        </div>
                        <div class="vision-card">
                            <h4>Our Vision</h4>
                            <p>To be recognized as a leading educational institution that fosters academic excellence, critical thinking, creativity, and ethical values in every student. We aspire to create a community of learners who are prepared to face global challenges with confidence and integrity.</p>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    team: {
        title: 'Our Team',
        html: `
            <div class="section about-section">
                <div class="container">
                    <h2 class="section-title">Our Team</h2>
                    <p class="section-subtitle">Dedicated Educators & Staff</p>
                    <div class="team-grid">
                        <div class="team-card">
                            <img src="assets/team1.jpg" alt="Senior Teacher">
                            <h4>Mr. Ram Kumar</h4>
                            <p>Mathematics Department Head</p>
                        </div>
                        <div class="team-card">
                            <img src="assets/team2.jpg" alt="Science Teacher">
                            <h4>Ms. Gita Sharma</h4>
                            <p>Science Department Head</p>
                        </div>
                        <div class="team-card">
                            <img src="assets/team3.jpg" alt="English Teacher">
                            <h4>Mr. Ashok Singh</h4>
                            <p>English Department Head</p>
                        </div>
                        <div class="team-card">
                            <img src="assets/team4.jpg" alt="Counselor">
                            <h4>Ms. Priya Rao</h4>
                            <p>School Counselor & Student Welfare</p>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    principal: {
        title: "Principal's Message",
        html: `
            <div class="section about-section">
                <div class="container">
                    <h2 class="section-title">Principal's Message</h2>
                    <div class="principal-message">
                        <img src="assets/principal.jpg" alt="Principal">
                        <div class="message-text">
                            <p><strong>"Dear Parents, Students, and Guardians,"</strong></p>
                            <p>It is with great pride that I welcome you to Kashyap Vidyapeeth Inaruwa. Our institution is committed to nurturing young minds and building future leaders. We believe education is not just about academic excellence but also about developing character, integrity, and social responsibility.</p>
                            <p>Our dedicated faculty works tirelessly to ensure every student reaches their full potential. We provide a holistic learning environment that encourages critical thinking, creativity, and compassion. Together, let us create a brighter tomorrow for our students and our nation.</p>
                            <p><strong>With warm regards,</strong><br>Dr. Rajendra Nath Mishra<br>Principal, Kashyap Vidyapeeth Inaruwa</p>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    academics: {
        title: 'Academics',
        html: `
            <div class="section academics-section">
                <div class="container">
                    <h2 class="section-title">Academics</h2>
                    <p class="section-subtitle">Comprehensive Curriculum for All Grades</p>
                    <div class="academics-grid">
                        <div class="academics-card">
                            <h3>Pre-Primary (PG)</h3>
                            <ul>
                                <li>Play-based Learning</li>
                                <li>Early Literacy & Numeracy</li>
                                <li>Creative Arts & Crafts</li>
                                <li>Social Development</li>
                                <li>Music & Movement Activities</li>
                            </ul>
                        </div>
                        <div class="academics-card">
                            <h3>Primary (Grades 1-5)</h3>
                            <ul>
                                <li>Core Subjects: English, Nepali, Math, Science</li>
                                <li>Social Studies & Civics</li>
                                <li>Physical Education & Sports</li>
                                <li>Computer Lab & Digital Literacy</li>
                                <li>Arts & Cultural Activities</li>
                            </ul>
                        </div>
                        <div class="academics-card">
                            <h3>Secondary (Grades 6-10)</h3>
                            <ul>
                                <li>Advanced Science & Mathematics</li>
                                <li>Arts & Commerce Streams</li>
                                <li>Laboratory Practice & Research</li>
                                <li>Board Exam Preparation</li>
                                <li>Competitive Exam Coaching</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    life: {
        title: 'Life at KVI',
        html: `
            <div class="section life-section">
                <div class="container">
                    <h2 class="section-title">Life at KVI</h2>
                    <p class="section-subtitle">Beyond Academics - Holistic Development</p>
                    <div class="life-grid">
                        <div class="life-card">
                            <div class="life-icon">⚽</div>
                            <h3>Sports & Athletics</h3>
                            <p>Football, Volleyball, Basketball, Badminton, Cricket, Table Tennis, and more. We encourage every student to participate in at least one sport.</p>
                        </div>
                        <div class="life-card">
                            <div class="life-icon">🎨</div>
                            <h3>Arts & Culture</h3>
                            <p>Painting, Dance, Music, Drama, and Cultural Festivals. Our students showcase their talents in various cultural programs throughout the year.</p>
                        </div>
                        <div class="life-card">
                            <div class="life-icon">💻</div>
                            <h3>Tech & Innovation</h3>
                            <p>Coding Club, Robotics, STEM Activities, Digital Lab. We prepare students for the digital age with cutting-edge technology.</p>
                        </div>
                        <div class="life-card">
                            <div class="life-icon">📖</div>
                            <h3>Literary Society</h3>
                            <p>Debate, Quiz, Essay Writing, Library Resources. Students develop communication and analytical skills through literary activities.</p>
                        </div>
                        <div class="life-card">
                            <div class="life-icon">🌍</div>
                            <h3>Social Service</h3>
                            <p>Community Outreach, Environmental Programs, Charity Drives. We instill values of social responsibility and empathy.</p>
                        </div>
                        <div class="life-card">
                            <div class="life-icon">🎓</div>
                            <h3>Leadership Programs</h3>
                            <p>Student Council, Mentoring, Team Building Workshops. We develop future leaders with strong values and vision.</p>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    'image-gallery': {
        title: 'Image Gallery',
        html: `
            <div class="section gallery-section">
                <div class="container">
                    <h2 class="section-title">Image Gallery</h2>
                    <p class="section-subtitle">Moments from Kashyap Vidyapeeth</p>
                    <div class="image-gallery-grid">
                        <div class="gallery-item" onclick="openImageModal('assets/gallery1.jpg', 'Campus View')">
                            <img src="assets/gallery1.jpg" alt="Campus View">
                            <div class="overlay">
                                <span>📷 Click to View</span>
                            </div>
                        </div>
                        <div class="gallery-item" onclick="openImageModal('assets/gallery2.jpg', 'Classroom Session')">
                            <img src="assets/gallery2.jpg" alt="Classroom Session">
                            <div class="overlay">
                                <span>📷 Click to View</span>
                            </div>
                        </div>
                        <div class="gallery-item" onclick="openImageModal('assets/gallery3.jpg', 'Sports Event')">
                            <img src="assets/gallery3.jpg" alt="Sports Event">
                            <div class="overlay">
                                <span>📷 Click to View</span>
                            </div>
                        </div>
                        <div class="gallery-item" onclick="openImageModal('assets/gallery4.jpg', 'Annual Function')">
                            <img src="assets/gallery4.jpg" alt="Annual Function">
                            <div class="overlay">
                                <span>📷 Click to View</span>
                            </div>
                        </div>
                        <div class="gallery-item" onclick="openImageModal('assets/gallery5.jpg', 'Science Lab')">
                            <img src="assets/gallery5.jpg" alt="Science Lab">
                            <div class="overlay">
                                <span>📷 Click to View</span>
                            </div>
                        </div>
                        <div class="gallery-item" onclick="openImageModal('assets/gallery6.jpg', 'Cultural Program')">
                            <img src="assets/gallery6.jpg" alt="Cultural Program">
                            <div class="overlay">
                                <span>📷 Click to View</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    'video-gallery': {
        title: 'Video Gallery',
        html: `
            <div class="section gallery-section">
                <div class="container">
                    <h2 class="section-title">Video Gallery</h2>
                    <p class="section-subtitle">School Videos & Events</p>
                    <div class="video-gallery-grid">
                        <div class="video-container">
                            <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" frameborder="0" allowfullscreen></iframe>
                            <p>School Overview - 2026</p>
                        </div>
                        <div class="video-container">
                            <iframe src="https://www.youtube.com/embed/9bZkp7q19f0" frameborder="0" allowfullscreen></iframe>
                            <p>Annual Sports Day Highlights</p>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    downloads: {
        title: 'Downloads',
        html: `
            <div class="section downloads-section">
                <div class="container">
                    <h2 class="section-title">Downloads</h2>
                    <p class="section-subtitle">Important Documents & Forms</p>
                    <div class="downloads-grid">
                        <div class="download-card">
                            <div class="download-icon">📋</div>
                            <h3>Admission Form</h3>
                            <p>Complete admission form for new students</p>
                            <a href="downloads/admission-form.pdf" class="download-btn" download>📥 Download PDF</a>
                        </div>
                        <div class="download-card">
                            <div class="download-icon">📚</div>
                            <h3>School Prospectus</h3>
                            <p>Comprehensive school information and programs</p>
                            <a href="downloads/prospectus.pdf" class="download-btn" download>📥 Download PDF</a>
                        </div>
                        <div class="download-card">
                            <div class="download-icon">📜</div>
                            <h3>Academic Calendar</h3>
                            <p>2026-27 Academic year schedule</p>
                            <a href="downloads/academic-calendar.pdf" class="download-btn" download>📥 Download PDF</a>
                        </div>
                        <div class="download-card">
                            <div class="download-icon">📋</div>
                            <h3>Fee Structure</h3>
                            <p>Detailed fee information for all grades</p>
                            <a href="downloads/fee-structure.pdf" class="download-btn" download>📥 Download PDF</a>
                        </div>
                        <div class="download-card">
                            <div class="download-icon">📖</div>
                            <h3>Code of Conduct</h3>
                            <p>Student discipline and conduct guidelines</p>
                            <a href="downloads/code-of-conduct.pdf" class="download-btn" download>📥 Download PDF</a>
                        </div>
                        <div class="download-card">
                            <div class="download-icon">🎯</div>
                            <h3>Curriculum Overview</h3>
                            <p>Detailed curriculum for all grades</p>
                            <a href="downloads/curriculum.pdf" class="download-btn" download>📥 Download PDF</a>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    contact: {
        title: 'Contact Us',
        html: `
            <div class="section contact-section">
                <div class="container">
                    <h2 class="section-title">Contact Us</h2>
                    <div class="contact-content">
                        <div class="contact-info-block">
                            <h3>Get in Touch</h3>
                            <div class="info-item">
                                <span class="info-icon">📍</span>
                                <div>
                                    <h4>Address</h4>
                                    <p>Inaruwa-4, Sunsari, Nepal</p>
                                </div>
                            </div>
                            <div class="info-item">
                                <span class="info-icon">📞</span>
                                <div>
                                    <h4>Phone</h4>
                                    <p>+977-9802779301<br>+977-9802779302<br>+977-9802779303</p>
                                </div>
                            </div>
                            <div class="info-item">
                                <span class="info-icon">✉️</span>
                                <div>
                                    <h4>Email</h4>
                                    <p>kvnepal@gmail.com<br>info@kvnepal.edu.np</p>
                                </div>
                            </div>
                            <div class="info-item">
                                <span class="info-icon">🕐</span>
                                <div>
                                    <h4>Office Hours</h4>
                                    <p>Monday - Friday: 8:00 AM - 4:00 PM<br>Saturday: 9:00 AM - 12:00 PM</p>
                                </div>
                            </div>
                        </div>
                        <form class="contact-form" id="contactForm" onsubmit="handleContactForm(event)">
                            <h3>Send us a Message</h3>
                            <div class="form-group">
                                <input type="text" placeholder="Your Name" id="name" required>
                            </div>
                            <div class="form-group">
                                <input type="email" placeholder="Your Email" id="email" required>
                            </div>
                            <div class="form-group">
                                <input type="tel" placeholder="Your Phone" id="phone">
                            </div>
                            <div class="form-group">
                                <select id="subject" required>
                                    <option value="">Select Subject</option>
                                    <option value="admission">Admission Inquiry</option>
                                    <option value="academics">Academic Query</option>
                                    <option value="event">Event Information</option>
                                    <option value="general">General Inquiry</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <textarea placeholder="Your Message" id="message" rows="5" required></textarea>
                            </div>
                            <button type="submit" class="btn btn-primary">Send Message</button>
                        </form>
                    </div>
                    <div class="map-container">
                        <h3>Our Location</h3>
                        <iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3522.3699999999996!2d87.3109!3d26.9647!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x39ee54e1234567!2sInaruwa!5e0!3m2!1sen!2snp!4v1234567890" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
                    </div>
                </div>
            </div>
        `
    }
};

// Chat responses data
const chatResponses = {
    greeting: [
        'Hello! 👋 How can I assist you today?',
        'Hi there! What would you like to know about Kashyap Vidyapeeth?',
        'Welcome! Feel free to ask any questions about our school.'
    ],
    admission: [
        'Admissions are currently open for Academic Year 2026-27. Please visit our Contact page or download the Admission Form from the Downloads section.',
        'You can contact us at +977-9802779301 or email kvnepal@gmail.com for admission details.',
        'We accept students from PG to Grade 10. Visit our About section for more details.'
    ],
    academics: [
        'We offer comprehensive programs from Pre-Primary to Grade 10, including Science and Commerce streams for higher grades.',
        'Our curriculum focuses on both academic excellence and holistic development of students.',
        'Visit the Academics section to learn about our courses and programs.'
    ],
    contact: [
        'You can reach us at +977-9802779301 or email kvnepal@gmail.com. We\'re located in Inaruwa-4, Sunsari, Nepal.',
        'Our office hours are Monday-Friday 8:00 AM - 4:00 PM and Saturday 9:00 AM - 12:00 PM.',
        'Use the Contact form below or call us directly with any queries.'
    ],
    events: [
        'Our Annual Sports Day is coming up on March 15, 2026! It\'s a great celebration of athletics and culture.',
        'We have exciting events throughout the year including cultural programs, debates, and sports competitions.',
        'Check our home page for announcements about upcoming events.'
    ],
    default: [
        'That\'s interesting! You can explore our different sections to learn more about Kashyap Vidyapeeth.',
        'Feel free to navigate through our menu to find what you\'re looking for.',
        'Is there anything specific about the school you\'d like to know? Try our About, Academics, or Gallery sections!'
    ]
};

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', function () {
    initializeMenuToggle();
    setupChatWidget();
    loadContent('home');
    showEventModalOnLoad();
});

// ============================================
// LOAD CONTENT DYNAMICALLY
// ============================================

function loadContent(page) {
    const mainContent = document.getElementById('main-content');
    const content = contentData[page];
    
    if (content) {
        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
        
        // Load content with fade-in effect
        mainContent.innerHTML = content.html;
        
        // Close mobile menu if open
        closeMenu();
        
        // Add chat message
        if (page !== 'home') {
            addChatMessage(`Great! I've loaded the ${content.title} section for you.`, 'bot');
        }
    }
}

// ============================================
// MENU TOGGLE (MOBILE)
// ============================================

function initializeMenuToggle() {
    const menuToggle = document.getElementById('menuToggle');
    const navMenu = document.getElementById('navMenu');

    menuToggle.addEventListener('click', function () {
        navMenu.classList.toggle('active');
        menuToggle.textContent = navMenu.classList.contains('active') ? '✕' : '☰';
    });

    // Close menu when a link is clicked
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function () {
            navMenu.classList.remove('active');
            menuToggle.textContent = '☰';
        });
    });

    // Handle dropdown menu toggle on mobile
    const dropdowns = document.querySelectorAll('.dropdown');
    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.dropdown-toggle');
        toggle.addEventListener('click', function (e) {
            if (window.innerWidth <= 768) {
                e.preventDefault();
                this.parentElement.classList.toggle('active');
            }
        });
    });
}

function closeMenu() {
    const navMenu = document.getElementById('navMenu');
    const menuToggle = document.getElementById('menuToggle');
    navMenu.classList.remove('active');
    menuToggle.textContent = '☰';
}

// ============================================
// CHAT WIDGET
// ============================================

function setupChatWidget() {
    const chatToggle = document.getElementById('chatToggle');
    const chatWidget = document.getElementById('chatWidget');
    const chatClose = document.getElementById('chatClose');
    const chatSend = document.getElementById('chatSend');
    const chatInput = document.getElementById('chatInput');

    // Toggle chat widget
    chatToggle.addEventListener('click', () => {
        chatWidget.classList.toggle('show');
    });

    // Close chat widget
    chatClose.addEventListener('click', () => {
        chatWidget.classList.remove('show');
    });

    // Send message on Enter key
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            chatSend.click();
        }
    });

    // Send chat message
    chatSend.addEventListener('click', () => {
        const message = chatInput.value.trim();
        if (message) {
            addChatMessage(message, 'user');
            chatInput.value = '';
            
            // Simulate bot response
            setTimeout(() => {
                const botResponse = generateChatResponse(message);
                addChatMessage(botResponse, 'bot');
            }, 500);
        }
    });
}

function addChatMessage(message, sender) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}-message`;
    messageDiv.innerHTML = `<p>${escapeHtml(message)}</p>`;
    chatMessages.appendChild(messageDiv);
    
    // Auto-scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function generateChatResponse(userMessage) {
    const lowerMessage = userMessage.toLowerCase();
    
    // Check for keywords
    if (lowerMessage.includes('admission') || lowerMessage.includes('admit') || lowerMessage.includes('apply')) {
        return chatResponses.admission[Math.floor(Math.random() * chatResponses.admission.length)];
    } else if (lowerMessage.includes('academic') || lowerMessage.includes('course') || lowerMessage.includes('subject')) {
        return chatResponses.academics[Math.floor(Math.random() * chatResponses.academics.length)];
    } else if (lowerMessage.includes('contact') || lowerMessage.includes('call') || lowerMessage.includes('email')) {
        return chatResponses.contact[Math.floor(Math.random() * chatResponses.contact.length)];
    } else if (lowerMessage.includes('event') || lowerMessage.includes('sports') || lowerMessage.includes('festival')) {
        return chatResponses.events[Math.floor(Math.random() * chatResponses.events.length)];
    } else if (lowerMessage.includes('hi') || lowerMessage.includes('hello') || lowerMessage.includes('hey')) {
        return chatResponses.greeting[Math.floor(Math.random() * chatResponses.greeting.length)];
    } else {
        return chatResponses.default[Math.floor(Math.random() * chatResponses.default.length)];
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// IMAGE GALLERY & LIGHTBOX
// ============================================

let currentImageIndex = 0;
const galleryImages = [
    'assets/gallery1.jpg',
    'assets/gallery2.jpg',
    'assets/gallery3.jpg',
    'assets/gallery4.jpg',
    'assets/gallery5.jpg',
    'assets/gallery6.jpg'
];

function openImageModal(imageSrc, caption) {
    const imageModal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    const captionText = document.getElementById('caption');

    modalImage.src = imageSrc;
    captionText.textContent = caption;
    imageModal.classList.add('show');

    currentImageIndex = galleryImages.findIndex(img => img === imageSrc);
}

function closeImageModal() {
    const imageModal = document.getElementById('imageModal');
    imageModal.classList.remove('show');
}

function nextImage() {
    currentImageIndex = (currentImageIndex + 1) % galleryImages.length;
    const modalImage = document.getElementById('modalImage');
    const captionText = document.getElementById('caption');
    const captions = ['Campus View', 'Classroom Session', 'Sports Event', 'Annual Function', 'Science Lab', 'Cultural Program'];
    
    modalImage.src = galleryImages[currentImageIndex];
    captionText.textContent = captions[currentImageIndex];
}

function previousImage() {
    currentImageIndex = (currentImageIndex - 1 + galleryImages.length) % galleryImages.length;
    const modalImage = document.getElementById('modalImage');
    const captionText = document.getElementById('caption');
    const captions = ['Campus View', 'Classroom Session', 'Sports Event', 'Annual Function', 'Science Lab', 'Cultural Program'];
    
    modalImage.src = galleryImages[currentImageIndex];
    captionText.textContent = captions[currentImageIndex];
}

window.addEventListener('click', function (event) {
    const imageModal = document.getElementById('imageModal');
    if (event.target === imageModal) {
        closeImageModal();
    }
});

document.addEventListener('keydown', function (event) {
    const imageModal = document.getElementById('imageModal');
    if (imageModal.classList.contains('show')) {
        if (event.key === 'ArrowLeft') {
            previousImage();
        } else if (event.key === 'ArrowRight') {
            nextImage();
        } else if (event.key === 'Escape') {
            closeImageModal();
        }
    }
});

// ============================================
// CONTACT FORM
// ============================================

function handleContactForm(event) {
    event.preventDefault();

    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('email').value.trim();
    const phone = document.getElementById('phone').value.trim();
    const subject = document.getElementById('subject').value;
    const message = document.getElementById('message').value.trim();

    if (!name || !email || !subject || !message) {
        showToast('Please fill in all required fields.', 'error');
        return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showToast('Please enter a valid email address.', 'error');
        return;
    }

    if (phone && !/^[\d\s\-\+\(\)]+$/.test(phone)) {
        showToast('Please enter a valid phone number.', 'error');
        return;
    }

    showToast(`Thank you, ${name}! Your message has been sent successfully. We will contact you soon.`, 'success');
    document.getElementById('contactForm').reset();
    addChatMessage(`Great! I've received your inquiry. Our team will contact you at ${email} soon.`, 'bot');
}

// ============================================
// TOAST NOTIFICATIONS
// ============================================

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');

    if (type === 'success') {
        toast.style.backgroundColor = '#28a745';
    } else if (type === 'error') {
        toast.style.backgroundColor = '#dc3545';
    } else {
        toast.style.backgroundColor = '#003d7a';
    }

    setTimeout(() => {
        toast.classList.remove('show');
        toast.classList.add('hide');
        setTimeout(() => {
            toast.classList.remove('hide');
            toast.style.backgroundColor = '#003d7a';
        }, 300);
    }, 4000);
}

// ============================================
// EVENT MODAL
// ============================================

function showEventModalOnLoad() {
    setTimeout(() => {
        showEventModal();
    }, 2000);
}

function showEventModal() {
    const eventModal = document.getElementById('eventModal');
    eventModal.classList.add('show');
}

function closeEventModal() {
    const eventModal = document.getElementById('eventModal');
    eventModal.classList.remove('show');
}

window.addEventListener('click', function (event) {
    const eventModal = document.getElementById('eventModal');
    if (event.target === eventModal) {
        closeEventModal();
    }
});

// ============================================
// UTILITY
// ============================================

console.log('Kashyap Vidyapeeth Inaruwa Website Loaded Successfully ✓');
console.log('Features:', [
    '✓ Dynamic Content Loading',
    '✓ Chat Widget',
    '✓ Mobile Responsive',
    '✓ Image Gallery Lightbox',
    '✓ Contact Form Validation',
    '✓ Toast Notifications',
    '✓ Event Modal',
    '✓ Keyboard Navigation'
]);