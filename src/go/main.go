// GenServer project main.go
package main

import (
	"fmt"
	"sync"
)

// ====================================================================
// PRIVATE
// Task dictionary
// This will be accessed from multiple threads
//
// Holds refs in the form {name: [gen-server, dispatcher, queue]}
var gs_desc = map[string]string{}

// Task dict lock
var gs_mu sync.Mutex

// ====================================================================
// PUBLIC
// API
func main() {
	gs_mu.Lock()
	fmt.Println("Hello World!")
	gs_mu.Unlock()
}
