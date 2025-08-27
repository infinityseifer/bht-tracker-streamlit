// 📌 Handles live character count for Narrative
document.getElementById("Narrative").addEventListener("input", function () {
  const counter = document.getElementById("narrativeCounter");
  counter.textContent = `${this.value.length} / 2500`;
});

// 📌 Handles preview before submission
document.getElementById("previewBtn").addEventListener("click", function () {
  const form = document.getElementById("DrForm");
  const formData = new FormData(form);
  const data = Object.fromEntries(formData.entries());

  /* Collect checkboxes
  data.TierOne = Array.from(document.querySelectorAll('input[name="TierOne"]:checked')).map(cb => cb.value);
  data.TierTwo = Array.from(document.querySelectorAll('input[name="TierTwo"]:checked')).map(cb => cb.value);
  data.TierThree = Array.from(document.querySelectorAll('input[name="TierThree"]:checked')).map(cb => cb.value);  */

  // Format datetime
  if (data.DateTime) {
    data.DateTime = new Date(data.DateTime).toISOString();
  }

  // Show preview
  const previewSection = document.getElementById("previewSection");
  const previewContent = document.getElementById("previewContent");
  previewContent.textContent = JSON.stringify(data, null, 2); // pretty print JSON
  previewSection.style.display = "block";

  // Save data globally for final submit
  window.previewFormData = data;
});

// 📌 Handles final confirmed submit
document.getElementById("confirmSubmitBtn").addEventListener("click", async function () {
  const data = window.previewFormData;

  try {
    const response = await fetch("http://localhost:5210/api/DrForm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });

    const result = await response.json();
    alert(result.message);
    document.getElementById("previewSection").style.display = "none";
    document.getElementById("DrForm").reset(); // Clear the form
  } catch (err) {
    console.error(err);
    alert("There was an error submitting the form.");
  }
});

// ❌ DO NOT add submit handler here anymore — we use confirmSubmitBtn instead
// document.getElementById("DrForm").addEventListener("submit", ...)
