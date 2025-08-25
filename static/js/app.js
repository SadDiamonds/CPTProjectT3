// Dark/Light Mode Toggle
const toggleBtn = document.querySelectorAll('#toggleBtn');
toggleBtn.forEach(btn => {
  btn.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
  });
});

// Form Submission Feedback
const addForm = document.getElementById('addForm');
if (addForm) {
  addForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const itemName = document.getElementById('itemName').value;
    document.getElementById('feedback').textContent = `You added: ${itemName}`;
    addForm.reset();
  });
}
