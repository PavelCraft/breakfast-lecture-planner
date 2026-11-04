document.querySelectorAll("[data-faq-carousel]").forEach((carousel) => {
  const slides = Array.from(carousel.querySelectorAll("[data-faq-slide]"));
  const dots = Array.from(carousel.querySelectorAll("[data-faq-dot]"));
  const previousButton = carousel.querySelector("[data-faq-prev]");
  const nextButton = carousel.querySelector("[data-faq-next]");
  const counter = carousel.querySelector("[data-faq-counter]");
  let currentIndex = 0;

  const showSlide = (index) => {
    currentIndex = Math.max(0, Math.min(index, slides.length - 1));

    slides.forEach((slide, slideIndex) => {
      slide.hidden = slideIndex !== currentIndex;
    });
    dots.forEach((dot, dotIndex) => {
      if (dotIndex === currentIndex) {
        dot.setAttribute("aria-current", "step");
      } else {
        dot.removeAttribute("aria-current");
      }
    });

    previousButton.disabled = currentIndex === 0;
    nextButton.disabled = currentIndex === slides.length - 1;
    counter.textContent = `Шаг ${currentIndex + 1} из ${slides.length}`;
  };

  previousButton.addEventListener("click", () => showSlide(currentIndex - 1));
  nextButton.addEventListener("click", () => showSlide(currentIndex + 1));
  dots.forEach((dot, index) => dot.addEventListener("click", () => showSlide(index)));

  carousel.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
      showSlide(currentIndex - 1);
    } else if (event.key === "ArrowRight") {
      showSlide(currentIndex + 1);
    } else {
      return;
    }
    event.preventDefault();
  });

  showSlide(0);
});
