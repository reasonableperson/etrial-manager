document.addEventListener('DOMContentLoaded', function () { 

  // If the page has any notifications on it, fade them out after 3 seconds.
  const flashes = document.getElementById('flashes')
  if (flashes) {
    flashes.style.opacity = 1
    setTimeout(() => { flashes.style.opacity = 0 }, 3000)
  }

  // #drag-drop-overlay is an absolutely-positioned div with partial opacity
  // which covers the entire viewport and is not displayed by default. These
  // functions can be used to 'highlight' the viewport, to indicate that it is
  // ready to receive a dropped file, by making #highlight visible.
  const overlay = document.getElementById('drag-drop-overlay')
  const highlight = function (event)  {
    event.preventDefault()
    overlay.classList.add('active')
  } 
  const unhighlight = function (event) {
    if (event) event.preventDefault()
    overlay.classList.remove('active')
  }

  // Given a drop event, call upload() once for each file
  const handleDroppedFiles = function (event) {
    event.preventDefault()
    unhighlight()
    const files = event.dataTransfer.files
    for (var i = 0; i < files.length; i++) {
      upload(files[i])
      console.dir(files[i].name, files[i].size / 1024, files[i].type)
    }
  }

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
  const upload = function (file) {
    const url = '/documents/add?filename=' + encodeURIComponent(file.name)
    // Create an old-fashioned XMLHttpRequest, because the Fetch API doesn't
    // provide great support for sending back upload progress reports at this
    // stage. Note that this first listener is attached to the upload property,
    // not the XHR itself.
    var req = new XMLHttpRequest()
    const progressIndicator = createProgressIndicator(file)
    req.upload.addEventListener('progress', (e) => {
      progressIndicator.style.width = e.loaded / e.total * 100 + '%'
    })

    // Attach an event handler on the request itself to refresh the page when
    // the upload is done, provided a favourable response was received from the
    // backend.
    req.addEventListener('load', () => {
      if (req.status == 200) window.location = '?reverse'
      else console.error(req.response)
    })
    req.open('POST', url, true)
    req.send(file)
  }

  // Given a click event from the documents or users table, generate the correct
  // backend request by inspecting the clicked cell's data attributes.
  const handleMatrix = async function (e) {
    // don't do anything if the handler is fired by something other than a <td>
    if (e.target.tagName != "TD") return
    const d = e.target.dataset
    const url = [window.location.pathname, d.action, d.row, d.col].join('/')
    console.log(url)
    const response = await fetch(url, { 'method': 'POST' })
    if (response.status == 200) window.location.reload()
    else console.error(response)
  }

  // Attach click handlers to the specified elements, if they exist.
  const maybeAttach = (selector, _event, callback) => {
    const el = document.querySelector(selector)
    if (el != null) el.addEventListener(_event, callback, false)
  }
  maybeAttach('#documents', 'click', handleMatrix)
  maybeAttach('#users', 'click', handleMatrix)
  maybeAttach('.drag-drop-target', 'dragenter', highlight)
  maybeAttach('.drag-drop-target', 'dragover', highlight)
  maybeAttach('.drag-drop-target', 'dragleave', unhighlight)
  maybeAttach('.drag-drop-target', 'drop', handleDroppedFiles)

})
