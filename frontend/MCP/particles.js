// Particle System for Canvas Background
class ParticleSystem {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.particles = [];
        this.connections = [];
        this.mouse = { x: null, y: null, radius: 150 };

        this.colors = {
            bronze: { r: 214, g: 134, b: 49 },
            teal: { r: 61, g: 113, b: 126 },
            navy: { r: 11, g: 40, b: 57 }
        };

        this.init();
        this.animate();
        this.setupEventListeners();
    }

    init() {
        this.resizeCanvas();
        this.createParticles();
    }

    resizeCanvas() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    createParticles() {
        const numberOfParticles = Math.floor((this.canvas.width * this.canvas.height) / 15000);

        for (let i = 0; i < numberOfParticles; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                radius: Math.random() * 2 + 1,
                color: Math.random() > 0.5 ? this.colors.bronze : this.colors.teal,
                opacity: Math.random() * 0.5 + 0.3
            });
        }
    }

    setupEventListeners() {
        window.addEventListener('resize', () => {
            this.resizeCanvas();
            this.particles = [];
            this.createParticles();
        });

        window.addEventListener('mousemove', (e) => {
            this.mouse.x = e.clientX;
            this.mouse.y = e.clientY;
        });

        window.addEventListener('mouseout', () => {
            this.mouse.x = null;
            this.mouse.y = null;
        });
    }

    drawParticle(particle) {
        this.ctx.beginPath();
        this.ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
        this.ctx.fillStyle = `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, ${particle.opacity})`;
        this.ctx.fill();

        // Add glow effect
        this.ctx.shadowBlur = 10;
        this.ctx.shadowColor = `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, 0.5)`;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
    }

    connectParticles() {
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const dx = this.particles[i].x - this.particles[j].x;
                const dy = this.particles[i].y - this.particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < 120) {
                    const opacity = (1 - distance / 120) * 0.3;
                    this.ctx.beginPath();
                    this.ctx.strokeStyle = `rgba(${this.colors.bronze.r}, ${this.colors.bronze.g}, ${this.colors.bronze.b}, ${opacity})`;
                    this.ctx.lineWidth = 0.5;
                    this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
                    this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
                    this.ctx.stroke();
                }
            }
        }
    }

    updateParticle(particle) {
        // Boundary check and bounce
        if (particle.x + particle.radius > this.canvas.width || particle.x - particle.radius < 0) {
            particle.vx = -particle.vx;
        }
        if (particle.y + particle.radius > this.canvas.height || particle.y - particle.radius < 0) {
            particle.vy = -particle.vy;
        }

        // Mouse interaction
        if (this.mouse.x !== null && this.mouse.y !== null) {
            const dx = this.mouse.x - particle.x;
            const dy = this.mouse.y - particle.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < this.mouse.radius) {
                const angle = Math.atan2(dy, dx);
                const force = (this.mouse.radius - distance) / this.mouse.radius;
                const repelX = Math.cos(angle) * force * 2;
                const repelY = Math.sin(angle) * force * 2;

                particle.vx -= repelX;
                particle.vy -= repelY;
            }
        }

        // Apply velocity damping
        particle.vx *= 0.99;
        particle.vy *= 0.99;

        // Update position
        particle.x += particle.vx;
        particle.y += particle.vy;

        // Pulsing opacity
        particle.opacity = 0.3 + Math.sin(Date.now() * 0.001 + particle.x) * 0.2;
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw gradient background
        const gradient = this.ctx.createRadialGradient(
            this.canvas.width / 2,
            this.canvas.height / 2,
            0,
            this.canvas.width / 2,
            this.canvas.height / 2,
            this.canvas.width / 2
        );
        gradient.addColorStop(0, 'rgba(11, 40, 57, 0.05)');
        gradient.addColorStop(1, 'rgba(10, 14, 26, 0)');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Update and draw particles
        this.particles.forEach(particle => {
            this.updateParticle(particle);
            this.drawParticle(particle);
        });

        // Draw connections
        this.connectParticles();

        // Draw mouse glow
        if (this.mouse.x !== null && this.mouse.y !== null) {
            const mouseGradient = this.ctx.createRadialGradient(
                this.mouse.x, this.mouse.y, 0,
                this.mouse.x, this.mouse.y, this.mouse.radius
            );
            mouseGradient.addColorStop(0, 'rgba(214, 134, 49, 0.1)');
            mouseGradient.addColorStop(1, 'rgba(214, 134, 49, 0)');
            this.ctx.fillStyle = mouseGradient;
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        }

        requestAnimationFrame(() => this.animate());
    }
}

// Initialize particle system when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('particleCanvas');
    new ParticleSystem(canvas);
});
