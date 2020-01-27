document.addEventListener('DOMContentLoaded', function () { 

  // If the page has any notifications on it, fade them out after 3 seconds.
  const flashes = document.getElementById('flashes')
  if (flashes) {
    flashes.style.opacity = 1
    setTimeout(function () { flashes.style.opacity = 0 }, 3000)
  }

  // Disable the browser's built-in functionality. When a user drags a PDF onto
  // the window, it should be uploaded, not displayed.
  // Reference: https://stackoverflow.com/a/6756680/1402935
  const ignoreEvent = function (e) { e = e || event; e.preventDefault() }
  window.addEventListener('dragover', ignoreEvent)
  window.addEventListener('drop', ignoreEvent)

  // Highlight the documents table when the user drags a file onto the window,
  // by adding a class to the invisible overlay element.
  const overlay = document.getElementById('drag-drop-overlay')
  var dragCount = 0
  window.addEventListener('dragenter', function () {
    // The cursor may drag into an element, then into one of its child elements.
    // Keep track of the 'depth' of the drag event.
    dragCount = dragCount + 1
    overlay.classList.add('active')
  })
  window.addEventListener('dragleave', function () {
    dragCount = dragCount - 1
    // Only when the cursor has left the screen altogether ('clearing' all
    // previous dragenter events) should we disable the overlay.
    if (dragCount == 0) overlay.classList.remove('active')
  })

  // Given a drop event, call upload() once for each file. TODO: multiple file
  // upload doesn't work in Firefox.
  window.addEventListener('drop', function (event) {
    event.preventDefault()
    overlay.classList.remove('active')
    const files = event.dataTransfer.files
    console.log(files.length + " files", files)
    for (var i = 0; i < files.length; i++) {
      upload(files[i])
      console.dir(files[i].name, files[i].size / 1024, files[i].type)
    }
  })

  // Create a new row in the documents table to display the upload progress
  // indicator. Returns a div which should have its width adjusted to reflect
  // the progress of the upload.
  const createProgressIndicator = function (file) {
    // Make room in the table.
    var firstRow = document.querySelector('tbody tr')
    var newRow = document.createElement('TR')
    var newCell = document.createElement('TD')
    newCell.colSpan = 9
    newCell.innerText = file.name
    firstRow.parentNode.insertBefore(newRow, firstRow)
    newRow.appendChild(newCell)

    // Create and return the progress indicator.
    const size = Math.round(file.size / 1024).toLocaleString() + ' KiB'
    var progressIndicator = document.createElement('div')
    progressIndicator.className = "progress"
    newCell.appendChild(progressIndicator)
    return progressIndicator
  }

  // Given a file (and a single drag and drop event could yield multiple files),
  // upload it to the backend. 
  var uploadCount = 0
  const upload = function (file) {
    uploadCount = uploadCount + 1
    const url = '/documents/add?filename=' + encodeURIComponent(file.name)
    // Create an old-fashioned XMLHttpRequest, because the Fetch API doesn't
    // provide great support for sending back upload progress reports at this
    // stage. Note that this first listener is attached to the upload property,
    // not the XHR itself.
    var req = new XMLHttpRequest()
    const progressIndicator = createProgressIndicator(file)
    req.upload.addEventListener('progress', function (e) {
      progressIndicator.style.width = e.loaded / e.total * 100 + '%'
    })

    // When an upload finishes, decrement the count of remaining uploads, and
    // if it was the last upload, refresh the page.
    req.addEventListener('load', function () {
      if (req.status == 200) {
        uploadCount = uploadCount - 1
        if (uploadCount == 0) window.location.reload()
      }
      else { console.error(req.response) }
    })
    req.open('POST', url, true)
    req.send(file)
  }

  // Given a click event from the documents or users table, generate the correct
  // backend request by inspecting the clicked cell's data attributes.
  const handleMatrix = function (e) {
    // don't do anything if the handler is fired by something other than a <td>
    if (e.target.tagName != "TD" || !e.target.classList.contains("matrix")) return
    const d = e.target.dataset
    const url = [window.location.pathname, d.action, d.row, d.col].join('/')
    console.log(url)
    var req = new XMLHttpRequest()
    req.addEventListener('load', function () {
      if (req.status == 200) window.location.reload()
      else console.error(req.response)
    })
    req.open('POST', url, true)
    req.send()
  }

  // Attach click handlers to the specified elements, if they exist.
  const maybeAttach = function (selector, _event, callback) {
    const el = document.querySelector(selector)
    if (el != null) el.addEventListener(_event, callback, false)
  }
  maybeAttach('#documents', 'click', handleMatrix)
  maybeAttach('#users', 'click', handleMatrix)

})
