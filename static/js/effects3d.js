/* ==========================================================================
   3D EFFECTS ENGINE - Particle System, Tilt Effects, Counter Animations,
   Ripple Effects, and Intersection Observer Entrance Animations
   ========================================================================== */

const effects3D = {
  // Particle system disabled for clean static UI
  initParticles() {},

  // 3D tilt effect disabled for clean static UI
  initTiltEffect() {},

  // Button interaction styling
  initRippleEffect() {},

  // Counter Animation
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

  // Intersection Observer Entrance
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

  // Magnetic buttons disabled for clean static UI
  initMagneticButtons() {},

  // Parallax disabled for clean static UI
  initParallax() {},

  // INIT ALL
  init() {
    this.initRippleEffect();
    this.initScrollAnimations();

    // Re-run counter animation whenever stat values update
    const statObserver = new MutationObserver(() => this.animateCounters());
    document.querySelectorAll('.stat-value').forEach(el => {
      statObserver.observe(el, { childList: true });
    });

    console.log('Clean UI Engine initialized');
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
