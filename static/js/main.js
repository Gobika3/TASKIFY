document.addEventListener("DOMContentLoaded", function () {
  // Elements
  const modal = document.getElementById("taskModal");
  const addTaskBtn = document.getElementById("addTaskBtn");
  const closeModal = document.querySelector(".close");
  const assignTo = document.getElementById("assignTo");
  const currentUserId = document.getElementById("currentUserId").value;
  const currentUserName = document.getElementById("currentUserName").value;

  // Add Task Modal Handling
  addTaskBtn.addEventListener("click", () => (modal.style.display = "block"));
  closeModal.addEventListener("click", () => (modal.style.display = "none"));
  window.addEventListener("click", (event) => {
    if (event.target === modal) modal.style.display = "none";
  });

  // Handle "Self" Selection
  assignTo.addEventListener("change", function () {
    const selectedOptions = Array.from(assignTo.selectedOptions).map(
      (opt) => opt.value
    );

    if (selectedOptions.includes("self")) {
      let userExists = Array.from(assignTo.options).some(
        (opt) => opt.value === currentUserId
      );

      if (!userExists) {
        let newOption = document.createElement("option");
        newOption.value = currentUserId;
        newOption.textContent = currentUserName;
        newOption.selected = true;
        assignTo.appendChild(newOption);
      }

      assignTo.querySelector('option[value="self"]').selected = false;
    }
  });

  // **Real-Time Search Feature**
  const searchInput = document.getElementById("search-input");
  const resultsContainer = document.getElementById("search-results");

  searchInput.addEventListener("input", function () {
    let query = searchInput.value.trim();

    if (query.length > 0) {
      fetch(`/search-tasks/?q=${query}`)
        .then((response) => response.json())
        .then((data) => {
          resultsContainer.innerHTML = "";
          if (data.length > 0) {
            data.forEach((task) => {
              const taskElement = document.createElement("div");
              taskElement.classList.add("task-result");
              taskElement.innerHTML = `<strong>${task.task_name}</strong><br>${task.description}`;
              resultsContainer.appendChild(taskElement);
            });
          } else {
            resultsContainer.innerHTML = "<p>No matching tasks found.</p>";
          }
        })
        .catch((error) => console.error("Error fetching tasks:", error));
    } else {
      resultsContainer.innerHTML = "";
    }
  });

  // **Search Modal Handling**
  const searchModal = document.getElementById("search-modal");
  const searchBtn = document.getElementById("searchBtn");
  const closeSearchBtn = document.getElementById("close-search-modal");

  searchBtn.addEventListener("click", (event) => {
    event.preventDefault();
    searchModal.style.display = "block";
  });

  closeSearchBtn.addEventListener(
    "click",
    () => (searchModal.style.display = "none")
  );
  window.addEventListener("click", (event) => {
    if (event.target === searchModal) searchModal.style.display = "none";
  });
});
