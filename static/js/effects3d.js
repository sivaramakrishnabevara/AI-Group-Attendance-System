/* ==========================================================================
   3D EFFECTS ENGINE - Particle System, Tilt Effects, Counter Animations,
   Ripple Effects, and Intersection Observer Entrance Animations
   ========================================================================== */

const effects3D = {
  // ==================== PARTICLE SYSTEM ====================
  initParticles() {
    const canvas = document.getElementById('particleCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let particles = [];
    let mouse = { x: -1000, y: -1000 };
    const PARTICLE_COUNT = 80;
    const CONNECTION_DISTANCE = 140;

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    document.addEventListener('mousemove', (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    });

    class Particle {
      constructor() {
        this.reset();
      }
      reset() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.size = Math.random() * 2 + 0.5;
        this.speedX = (Math.random() - 0.5) * 0.6;
        this.speedY = (Math.random() - 0.5) * 0.6;
        this.opacity = Math.random() * 0.5 + 0.1;
        // color variety
        const colors = [
          [0, 242, 254],   // cyan
          [192, 132, 252], // purple
          [0, 230, 118],   // emerald
          [79, 172, 254],  // blue
        ];
        this.color = colors[Math.floor(Math.random() * colors.length)];
      }
      update() {
        this.x += this.speedX;
        this.y += this.speedY;

        // Mouse repulsion
        const dx = mouse.x - this.x;
        const dy = mouse.y - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          const force = (120 - dist) / 120;
          this.x -= dx * force * 0.02;
          this.y -= dy * force * 0.02;
        }

        // Wrap around edges
        if (this.x < -10) this.x = canvas.width + 10;
        if (this.x > canvas.width + 10) this.x = -10;
        if (this.y < -10) this.y = canvas.height + 10;
        if (this.y > canvas.height + 10) this.y = -10;
      }
      draw() {
        const [r, g, b] = this.color;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${this.opacity})`;
        ctx.fill();

        // Glow
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size * 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${this.opacity * 0.15})`;
        ctx.fill();
      }
    }

    // Initialize particles
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push(new Particle());
    }

    function drawConnections() {
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < CONNECTION_DISTANCE) {
            const opacity = (1 - dist / CONNECTION_DISTANCE) * 0.15;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(0, 242, 254, ${opacity})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }
    }

    function animate() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.update();
        p.draw();
      });
      drawConnections();
      requestAnimationFrame(animate);
    }
    animate();
  },

  // ==================== 3D TILT EFFECT ====================
  initTiltEffect() {
    const tiltElements = document.querySelectorAll('.tilt-3d');
    tiltElements.forEach(el => {
      el.addEventListener('mousemove', (e) => {
        const rect = el.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -8;
        const rotateY = ((x - centerX) / centerX) * 8;
        el.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(10px)`;
      });
      el.addEventListener('mouseleave', () => {
        el.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0)';
      });
    });
  },

  // ==================== RIPPLE EFFECT ON BUTTONS ====================
  initRippleEffect() {
    document.querySelectorAll('.btn').forEach(btn => {
      btn.classList.add('ripple-effect');
      btn.addEventListener('click', function(e) {
        const ripple = document.createElement('span');
        ripple.className = 'ripple';
        const rect = this.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        ripple.style.width = ripple.style.height = size + 'px';
        ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
        ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
        this.appendChild(ripple);
        setTimeout(() => ripple.remove(), 700);
      });
    });
  },

  // ==================== COUNTER ANIMATION ====================
  animateCounters() {
    const counters = document.querySelectorAll('.stat-value');
    counters.forEach(counter => {
      const target = parseInt(counter.textContent) || 0;
      if (target === 0 || counter.dataset.animated === 'true') return;
      counter.dataset.animated = 'true';
      let current = 0;
      const duration = 1200;
      const start = performance.now();
      function step(timestamp) {
        const progress = Math.min((timestamp - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        current = Math.floor(eased * target);
        counter.textContent = current;
        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          counter.textContent = target;
        }
      }
      requestAnimationFrame(step);
    });
  },

  // ==================== INTERSECTION OBSERVER ENTRANCE ====================
  initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('anim-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    document.querySelectorAll('.glass-card, .stat-card, .form-group').forEach(el => {
      el.classList.add('anim-observe');
      observer.observe(el);
    });
  },

  // ==================== MAGNETIC CURSOR EFFECT ON NAV ====================
  initMagneticButtons() {
    document.querySelectorAll('.brand-icon, .btn-primary, .btn-purple, .btn-emerald').forEach(el => {
      el.addEventListener('mousemove', (e) => {
        const rect = el.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        el.style.transform = `translate(${x * 0.15}px, ${y * 0.15}px)`;
      });
      el.addEventListener('mouseleave', () => {
        el.style.transform = '';
      });
    });
  },

  // ==================== SMOOTH PARALLAX ON SCROLL ====================
  initParallax() {
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          const scrollY = window.scrollY;
          const orbs = document.querySelectorAll('.floating-orb');
          orbs.forEach((orb, i) => {
            const speed = 0.02 + (i * 0.01);
            orb.style.transform += ` translateY(${scrollY * speed}px)`;
          });
          ticking = false;
        });
        ticking = true;
      }
    });
  },

  // ==================== INIT ALL ====================
  init() {
    this.initParticles();
    this.initTiltEffect();
    this.initRippleEffect();
    this.initScrollAnimations();
    this.initMagneticButtons();

    // Re-run counter animation whenever stat values update
    const statObserver = new MutationObserver(() => this.animateCounters());
    document.querySelectorAll('.stat-value').forEach(el => {
      statObserver.observe(el, { childList: true });
    });

    // Add 3D classes to existing elements
    document.querySelectorAll('.stat-card').forEach((card, i) => {
      card.classList.add('stat-card-3d', 'tilt-3d', 'anim-enter', `anim-delay-${i + 1}`);
    });

    document.querySelectorAll('.btn').forEach(btn => {
      btn.classList.add('btn-3d');
    });

    document.querySelectorAll('.form-control').forEach(input => {
      input.classList.add('form-control-3d');
    });

    // Add navbar 3D class
    const navbar = document.querySelector('.navbar');
    if (navbar) navbar.classList.add('navbar-3d');

    // Add holographic shimmer to login card
    const loginCard = document.querySelector('#loginScreen .glass-card');
    if (loginCard) {
      loginCard.classList.add('holo-shimmer', 'aurora-border', 'tilt-3d');
    }

    // Add webcam 3D
    document.querySelectorAll('.webcam-container').forEach(el => {
      el.classList.add('webcam-container-3d');
    });

    // Add tab button 3D
    document.querySelectorAll('[id^="tabBtn"], [id^="tabTeacherBtn"]').forEach(btn => {
      btn.classList.add('tab-3d');
    });

    // Live indicator 3D
    document.querySelectorAll('.live-indicator').forEach(el => {
      el.classList.add('live-indicator-3d');
    });

    console.log('🚀 3D Effects Engine initialized');
  }
};

// CSS for scroll-triggered animations (injected via JS)
const style3D = document.createElement('style');
style3D.textContent = `
  .anim-observe {
    opacity: 0;
    transform: translateY(40px) scale(0.97);
    transition: all 0.7s cubic-bezier(0.23, 1, 0.32, 1);
  }
  .anim-observe.anim-visible {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
`;
document.head.appendChild(style3D);
