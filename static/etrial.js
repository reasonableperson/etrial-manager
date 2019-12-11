document.addEventListener('DOMContentLoaded', function () { 

  // #dropzone-highlight is an absolutely-positioned div with partial opacity
  // which covers the entire viewport and is not displayed by default. These
  // functions can be used to 'highlight' the viewport, to indicate that it is
  // ready to receive a dropped file, by making #dropzone-highlight visible.
  const overlay = document.getElementById('dropzone-highlight')
  const highlight = function (event)  {
    event.preventDefault()
    overlay.classList.add('active')
  } 
  const unhighlight = function (event) {
    if (event) event.preventDefault()
    overlay.classList.remove('active')
  }

  // This handler is used to accept (upload) a dropped file.
  const accept = function (event) {
    event.preventDefault()
    unhighlight()
    const files = event.dataTransfer.files
    for (var i = 0; i < files.length; i++) {
      addUpload(files[i])
      console.dir(files[i].name, files[i].size / 1024, files[i].type)
    }
  }

  // Kill an upload by pressing the ×.
  const cancelUpload = function (event) {
    // This handler can be attached to the whole notifications section and it
    // will only run if the clicked item was actually the cancel button.
    if (event.target.className == 'cancel') {
      console.log(event.target.parentElement)
      event.target.parentElement.style.opacity = 0
      event.target.parentElement.addEventListener('transitionend', function (event) {
        event.target.outerHTML = ''
      })
    }
  }

  const createProgressHandler = (progressElem) => (e) => {
  }

  // Adds a new notification toast for a new file upload, and updates the
  // progress indicator as the file uploads?
  const addUpload = function (file) {
    const ul = document.getElementById('notifications').children[0]
    const size = Math.round(file.size / 1024).toLocaleString() + ' KiB'
    var li = document.createElement('LI')
    var progressIndicator = document.createElement('DIV')
    progressIndicator.className = "progress"
    li.innerHTML = file.name + ' (' + file.type + ', ' + size + ')' + 
      '<span class="cancel">×</span>'
    li.appendChild(progressIndicator)
    ul.appendChild(li)

    var req = new XMLHttpRequest()
    req.upload.addEventListener('load', () => { li.remove(); window.location.reload() })
    req.upload.addEventListener('progress', (e) => {
      progressIndicator.style.width = e.loaded / e.total * 100 + '%'
    })

    //reader.addEventListener('load', (e) => { req.send(e.target.result) })
    req.open('POST', '/upload?filename=' + encodeURIComponent(file.name), true)
    req.send(file)

    //reader.readAsBinaryString(file)

  }

  document.addEventListener('dragenter', highlight, false)
  document.addEventListener('dragleave', unhighlight, false)
  document.addEventListener('dragover', highlight, false)
  document.addEventListener('drop', accept, false)

  document.getElementById('notifications').addEventListener('click', cancelUpload, false)

})
